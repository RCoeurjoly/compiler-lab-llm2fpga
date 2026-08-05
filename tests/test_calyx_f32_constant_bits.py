import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "verify_calyx_f32_constant_bits.py"
SPEC = importlib.util.spec_from_file_location("calyx_f32_verifier", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def calyx_source(
    constants: str, component_header: str = "calyx.component @main() -> ()"
) -> str:
    return f"""module {{
  {component_header} {{
    {constants}
  }}
}}
"""


def futil_source(cells: str, component_name: str = "main") -> str:
    return f"""component {component_name}() -> () {{
  cells {{
    {cells}
  }}
}}
"""


def run_verifier(source: str, futil: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_path = tmp_path / "input.mlir"
        futil_path = tmp_path / "export.futil"
        receipt_path = tmp_path / "receipt.json"
        source_path.write_text(calyx_source(source), encoding="utf-8")
        futil_path.write_text(futil_source(futil), encoding="utf-8")
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--calyx-mlir",
                str(source_path),
                "--futil",
                str(futil_path),
                "--receipt",
                str(receipt_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )


def run_verifier_success(
    source: str,
    futil: str,
    component_header: str = "calyx.component @main() -> ()",
    futil_component_name: str = "main",
) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_path = tmp_path / "input.mlir"
        futil_path = tmp_path / "export.futil"
        receipt_path = tmp_path / "receipt.json"
        source_text = calyx_source(source, component_header)
        futil_text = futil_source(futil, futil_component_name)
        source_path.write_text(source_text, encoding="utf-8")
        futil_path.write_text(futil_text, encoding="utf-8")
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--calyx-mlir",
                str(source_path),
                "--futil",
                str(futil_path),
                "--receipt",
                str(receipt_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    self_source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    self_futil_hash = hashlib.sha256(futil_text.encode("utf-8")).hexdigest()
    if receipt["calyx_mlir_sha256"] != self_source_hash:
        raise AssertionError("receipt source hash is not the input SHA-256")
    if receipt["futil_sha256"] != self_futil_hash:
        raise AssertionError("receipt Futil hash is not the input SHA-256")
    return receipt


class CalyxF32ConstantBitsTest(unittest.TestCase):
    def test_accepts_exact_words_and_writes_sorted_receipt(self) -> None:
        receipt = run_verifier_success(
            source="""
%zeta = calyx.constant @zeta <4.200000e+00 : f32> : i32
%alpha = calyx.constant @alpha <0x7F800000 : f32> : i32
""",
            futil="""
zeta = std_const(32, 1082549862);
alpha = std_const(32, 2139095040);
""",
        )
        self.assertEqual(receipt["schema"], "rc-calyx-f32-constant-bits-v1")
        self.assertEqual(
            receipt["constants"],
            [
                {"component": "main", "symbol": "alpha", "word_u32": 2139095040},
                {"component": "main", "symbol": "zeta", "word_u32": 1082549862},
            ],
        )

    def test_rejects_tiny_nonzero_rewritten_as_zero(self) -> None:
        result = run_verifier(
            source="%tiny = calyx.constant @tiny <7.54663105e-08 : f32> : i32",
            futil="tiny = std_const(32, 0);",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("866258955", result.stderr)

    def test_accepts_exact_negative_zero_word(self) -> None:
        receipt = run_verifier_success(
            source="%neg_zero = calyx.constant @neg_zero <0x80000000 : f32> : i32",
            futil="neg_zero = std_const(32, 2147483648);",
        )
        self.assertEqual(receipt["constants"][0]["word_u32"], 2147483648)

    def test_accepts_constants_after_attributed_component_ports(self) -> None:
        receipt = run_verifier_success(
            source="%tiny = calyx.constant @tiny <7.54663105e-08 : f32> : i32",
            futil="tiny = std_const(32, 866258955);",
            component_header=(
                "calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, "
                "%go: i1 {go}) -> (%done: i1 {done})"
            ),
        )
        self.assertEqual(receipt["constants"][0]["word_u32"], 866258955)

    def test_preserves_component_identifier_ending_with_dollar_and_hyphen(self) -> None:
        receipt = run_verifier_success(
            source="%edge = calyx.constant @edge$- <1.0 : f32> : i32",
            futil="edge$- = std_const(32, 1065353216);",
            component_header="calyx.component @main$-() -> ()",
            futil_component_name="main$-",
        )
        self.assertEqual(
            receipt["constants"],
            [{"component": "main$-", "symbol": "edge$-", "word_u32": 1065353216}],
        )

    def test_preserves_nan_payload_as_raw_u32(self) -> None:
        receipt = run_verifier_success(
            source="%nan = calyx.constant @nan <0x7FC00001 : f32> : i32",
            futil="nan = std_const(32, 2143289345);",
        )
        self.assertEqual(receipt["constants"][0]["word_u32"], 2143289345)

    def test_decimal_rounding_boundaries_are_exact(self) -> None:
        cases = {
            "1.000000059604644775390625": 0x3F800000,
            "1.000000178813934326171875": 0x3F800002,
            "1e-46": 0x00000000,
            "1e-45": 0x00000001,
            "3.5e38": 0x7F800000,
        }
        for literal, expected_word in cases.items():
            with self.subTest(literal=literal):
                self.assertEqual(VERIFIER.decimal_literal_to_f32_word(literal), expected_word)

    def test_reports_no_component_body_as_verification_error(self) -> None:
        with self.assertRaises(VERIFIER.VerificationError):
            VERIFIER.parse_calyx_constants("calyx.component @main()")

    def test_rejects_missing_source_constant(self) -> None:
        result = run_verifier(
            source="""
%one = calyx.constant @one <1.0 : f32> : i32
%two = calyx.constant @two <2.0 : f32> : i32
""",
            futil="one = std_const(32, 1065353216);",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr)
        self.assertIn("two", result.stderr)

    def test_rejects_extra_futil_constant(self) -> None:
        result = run_verifier(
            source="%one = calyx.constant @one <1.0 : f32> : i32",
            futil="""
one = std_const(32, 1065353216);
extra = std_const(32, 0);
""",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("extra", result.stderr)

    def test_rejects_same_line_extra_futil_constant(self) -> None:
        result = run_verifier(
            source="%one = calyx.constant @one <1.0 : f32> : i32",
            futil="one = std_const(32, 1065353216); extra = std_const(32, 0);",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("extra", result.stderr)

    def test_rejects_duplicate_futil_constant(self) -> None:
        result = run_verifier(
            source="%one = calyx.constant @one <1.0 : f32> : i32",
            futil="""
one = std_const(32, 1065353216);
one = std_const(32, 1065353216);
""",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)

    def test_rejects_same_line_duplicate_futil_constant(self) -> None:
        result = run_verifier(
            source="%one = calyx.constant @one <1.0 : f32> : i32",
            futil="one = std_const(32, 1065353216); one = std_const(32, 1065353216);",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr)

    def test_rejects_non_32_bit_futil_constant(self) -> None:
        result = run_verifier(
            source="%one = calyx.constant @one <1.0 : f32> : i32",
            futil="one = std_const(16, 0);",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("width", result.stderr)

    def test_rejects_legacy_float_cell(self) -> None:
        result = run_verifier(
            source="%one = calyx.constant @one <1.0 : f32> : i32",
            futil="one = std_float_const(0, 32, 1.000000);",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("std_float_const", result.stderr)


if __name__ == "__main__":
    unittest.main()
