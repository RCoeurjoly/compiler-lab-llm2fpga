"""Contract tests for compiler-generated exact serial-GEMV Calyx IR.

These tests intentionally exercise a descriptor-sized slice.  They do not
accept a generic SCF lowering or a copied RTL implementation as evidence.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOWERER = ROOT / "scripts/pipeline/lower_exact_serial_gemv_to_calyx.py"
FIXTURE = ROOT / "reproducers/tinystories-1m-exact-serial-gemv/calyx-component.mlir"
REFERENCE_RTL = ROOT / "TinyStories" / "rtl"
GATE_VERIFIER = ROOT / "scripts/pipeline/verify_exact_serial_gemv_calyx_gate.py"


def _load_lowerer():
    spec = importlib.util.spec_from_file_location("serial_gemv_calyx", LOWERER)
    if spec is None or spec.loader is None:
        raise AssertionError("serial-GEMV Calyx lowerer is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_gate_verifier():
    spec = importlib.util.spec_from_file_location("serial_gemv_gate", GATE_VERIFIER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _descriptor(rows: int = 1, outputs: int = 64, inputs: int = 64) -> str:
    return (
        f'%0 = "llm2fpga.serial_gemv"(%input, %weights) '
        f'{{inputs = {inputs} : i64, mac_order = "ascending_i64_wrap", '
        f'outputs = {outputs} : i64, rows = {rows} : i64}} : '
        f'(tensor<{rows}x{inputs}xi64>, tensor<{outputs}x{inputs}xi64>) '
        f'-> tensor<{rows}x{outputs}xi64>'
    )


class ExactSerialGemvCalyxTest(unittest.TestCase):
    def test_component_and_invoke_are_generated_from_descriptor(self) -> None:
        lowerer = _load_lowerer()
        artifact = lowerer.lower_descriptor_text(_descriptor())
        self.assertIn("calyx.component @llm2fpga_serial_gemv_64_64", artifact.mlir)
        self.assertIn("calyx.invoke @llm2fpga_serial_gemv_instance", artifact.mlir)
        self.assertIn("calyx.std_mult", artifact.mlir)
        self.assertIn("calyx.std_add", artifact.mlir)
        self.assertIn("calyx.register @k_counter", artifact.mlir)
        self.assertIn("calyx.register @accumulator", artifact.mlir)
        self.assertNotIn("scf.for", artifact.mlir)

    def test_rows4_component_has_runtime_addresses_writeback_and_multiplier_wait(self) -> None:
        lowerer = _load_lowerer()
        artifact = lowerer.lower_descriptor_text(_descriptor(rows=4, outputs=50257, inputs=64))
        for required in (
            "calyx.register @row_counter",
            "calyx.register @activation_address",
            "calyx.register @weight_address",
            "calyx.register @result_address",
            "calyx.std_slice @activation_address_slice",
            "calyx.std_slice @weight_address_slice",
            "calyx.std_slice @result_address_slice",
            "calyx.group @read_operands",
            "calyx.group @launch_multiply",
            "calyx.group_done %mac_mul.done",
            "calyx.group @write_result",
            "calyx.assign %results.write_data = %accumulator.out : i64",
            "calyx.assign %results.write_en = %true : i1",
            "calyx.while %row_less.out with @row_not_done",
        ):
            self.assertIn(required, artifact.mlir)
        trace = lowerer.generated_component_trace_summary(artifact)
        self.assertEqual(trace["first"]["row"], 0)
        self.assertEqual(trace["last"]["row"], 3)
        self.assertEqual(trace["last"]["output"], 50256)
        self.assertEqual(trace["last"]["input"], 63)
        self.assertEqual(trace["last"]["result_address"], 4 * 50257 - 1)

    def test_gate_recomputes_trace_control_binding_from_calyx(self) -> None:
        lowerer = _load_lowerer()
        verifier = _load_gate_verifier()
        artifact = lowerer.lower_descriptor_text(_descriptor())
        expected = lowerer.generated_component_trace_summary(artifact)
        with tempfile.TemporaryDirectory(prefix="serial-gemv-control-") as temporary:
            path = Path(temporary) / "model.calyx.mlir"
            path.write_text(artifact.mlir, encoding="utf-8")
            self.assertEqual(verifier.emitted_trace_summary(path), {
                "descriptor": artifact.provenance["descriptor"], **expected
            })
            path.write_text(artifact.mlir.replace("@read_operands", "@mutated_read_operands", 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "runtime control"):
                verifier.emitted_trace_summary(path)

    def test_64x64_ordered_address_data_trace_is_stable(self) -> None:
        lowerer = _load_lowerer()
        descriptor = lowerer.parse_descriptor_text(_descriptor())
        trace = lowerer.serial_address_data_trace(descriptor)
        self.assertEqual(len(trace), 64 * 64)
        self.assertEqual(trace[0]["activation_address"], 0)
        self.assertEqual(trace[0]["weight_address"], 0)
        self.assertEqual(trace[1]["activation_address"], 1)
        self.assertEqual(trace[1]["weight_address"], 1)
        self.assertEqual(trace[64]["activation_address"], 0)
        self.assertEqual(trace[64]["weight_address"], 64)
        self.assertEqual(
            lowerer.trace_sha256(trace),
            "75f9d4bea7667be6a897a2171dcb3a9f4563124cc112c05fd4b2e09f43e1b932",
        )
        self.assertEqual(lowerer.stream_trace_sha256(descriptor), lowerer.trace_sha256(trace))

    def test_descriptor_without_ascending_wrap_is_rejected(self) -> None:
        lowerer = _load_lowerer()
        invalid = _descriptor().replace('mac_order = "ascending_i64_wrap", ', "")
        with self.assertRaisesRegex(ValueError, "ascending_i64_wrap"):
            lowerer.parse_descriptor_text(invalid)

    def test_generated_source_does_not_match_reference_rtl(self) -> None:
        lowerer = _load_lowerer()
        artifact = lowerer.lower_descriptor_text(_descriptor())
        generated_hash = hashlib.sha256(artifact.mlir.encode()).hexdigest()
        if REFERENCE_RTL.is_dir():
            rtl_hashes = {
                hashlib.sha256(path.read_bytes()).hexdigest()
                for path in REFERENCE_RTL.rglob("*")
                if path.is_file()
            }
        else:
            rtl_hashes = set()
        self.assertNotIn(generated_hash, rtl_hashes)
        self.assertIn("generated_from_descriptor", artifact.provenance)

    def test_reproducer_is_generated_and_parseable_when_circt_is_available(self) -> None:
        lowerer = _load_lowerer()
        expected = lowerer.lower_descriptor_text(_descriptor()).mlir
        self.assertEqual(FIXTURE.read_text(encoding="utf-8"), expected)
        circt_opt = lowerer.find_circt_opt()
        if circt_opt is None:
            self.skipTest("circt-opt is not available outside the Nix development shell")
        with tempfile.TemporaryDirectory(prefix="serial-gemv-calyx-") as temporary:
            source = Path(temporary) / "generated.mlir"
            output = Path(temporary) / "parsed.mlir"
            source.write_text(expected, encoding="utf-8")
            completed = subprocess.run(
                [str(circt_opt), str(source), "-o", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=1800,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
