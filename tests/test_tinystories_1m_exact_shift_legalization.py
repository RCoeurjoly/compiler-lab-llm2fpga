from __future__ import annotations

from dataclasses import dataclass
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "TinyStories/model_adapter_exact_package.py"
EXPECTED_ADAPTER_SHA256 = (
    "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e"
)
PATCH = ROOT / "patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch"
PLUGIN = ROOT / "tools/torch-mlir-passes/LegalizeBitwiseRightShiftTensorScalar.cpp"
RIGHT_SHIFT_REPRODUCER = (
    ROOT
    / "reproducers"
    / "tinystories-1m-exact-torch-mlir"
    / "bitwise-right-shift-tensor-scalar.mlir"
)
LEFT_SHIFT_REPRODUCER = (
    ROOT
    / "reproducers"
    / "tinystories-1m-exact-torch-mlir"
    / "bitwise-left-shift-tensor-scalar.mlir"
)


def implementation_source() -> str:
    implementations = [path for path in (PATCH, PLUGIN) if path.is_file()]
    if len(implementations) != 1:
        raise AssertionError(
            "expected exactly one Tensor_Scalar shift legalization implementation, "
            f"found {implementations}"
        )
    return implementations[0].read_text(encoding="utf-8")


def right_shift_module_text(
    *,
    input_type: str = "!torch.vtensor<[4,1],si64>",
    result_type: str = "!torch.vtensor<[4,1],si64>",
    count_definition: str = "%count = torch.constant.int 1",
) -> str:
    return f"""module {{
  func.func @main(%arg0: {input_type}) -> {result_type} {{
    {count_definition}
    %0 = torch.operator "torch.aten.bitwise_right_shift.Tensor_Scalar"(%arg0, %count) : ({input_type}, !torch.int) -> {result_type}
    return %0 : {result_type}
  }}
}}
"""


@dataclass(frozen=True)
class CompilerRun:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    output_created: bool
    output_text: str


class TinyStories1mExactShiftLegalizationTest(unittest.TestCase):
    def run_module(self, text: str, pipeline: str) -> CompilerRun:
        tool = shutil.which("torch-mlir-opt")
        self.assertIsNotNone(tool, "test must run inside the pinned Nix environment")
        with tempfile.TemporaryDirectory(prefix="exact-right-shift-runtime-") as temporary:
            source = Path(temporary) / "input.mlir"
            output = Path(temporary) / "output.mlir"
            source.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [str(tool), f"-pass-pipeline={pipeline}", str(source), "-o", str(output)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            output_created = output.is_file()
            return CompilerRun(
                args=result.args,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                output_created=output_created,
                output_text=output.read_text(encoding="utf-8") if output_created else "",
            )

    def assert_rejected_without_output(self, result: CompilerRun, diagnostic: str) -> None:
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(diagnostic, result.stderr)
        self.assertFalse(result.output_created, "rejected input unexpectedly created its -o file")
        self.assertEqual(result.stdout, "", "rejected input unexpectedly wrote compiler IR to stdout")

    def test_exact_adapter_identity_is_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(ADAPTER.read_bytes()).hexdigest(), EXPECTED_ADAPTER_SHA256)

    def test_pinned_torch_mlir_build_contains_the_legalization(self) -> None:
        source = implementation_source()
        torch_mlir_nix = (ROOT / "torch-mlir.nix").read_text(encoding="utf-8")
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        pipeline = (ROOT / "nix/pipeline.nix").read_text(encoding="utf-8")

        if PATCH.is_file():
            self.assertIn(
                "./patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch",
                torch_mlir_nix,
            )
        else:
            self.assertIn("torchMlirPasses", pipeline)
            self.assertIn("torch-mlir-passes.nix", flake)
        self.assertIn('rev = "59c249e5cc2025acca81bdcf1596b8dd36a5c0f9"', torch_mlir_nix)
        self.assertIn("torchMlir = pkgsLlvm21.callPackage ./torch-mlir.nix", flake)
        self.assertIn("torchMlir", pipeline)
        self.assertTrue(source)

    def test_legalization_precedes_the_failing_backend_pipeline(self) -> None:
        if PATCH.is_file():
            source = implementation_source()
            # Pinned source line 75 is createInlinerPass(); the failing
            # createReduceOpVariantsPass starts on line 76. The zero-context
            # patch must insert the legalization exactly between them.
            self.assertIn("@@ -75,0 +", source)
            self.assertIn(
                "std::make_unique<LegalizeBitwiseRightShiftTensorScalarPass>()",
                source,
            )
            return
        else:
            pipeline = (ROOT / "nix/pipeline.nix").read_text(encoding="utf-8")
            legalization = pipeline.find(
                "llm2fpga-legalize-bitwise-right-shift-tensor-scalar"
            )
            backend = pipeline.find(
                "torchdynamo-export-to-torch-backend-pipeline", legalization
            )
        self.assertGreaterEqual(legalization, 0)
        self.assertGreater(backend, legalization)

    def test_source_matches_only_the_exact_operator_and_signed_si64_tensor(self) -> None:
        source = implementation_source()
        right_shift_source = source[
            source.index("class LegalizeBitwiseRightShiftTensorScalarPass") :
            source.index("class LegalizeBitwiseLeftShiftTensorScalarPass")
        ]
        self.assertIn("torch.aten.bitwise_right_shift.Tensor_Scalar", right_shift_source)
        self.assertNotIn("torch.aten.bitwise_left_shift.Tensor_Scalar", right_shift_source)
        self.assertIn("ValueTensorType", right_shift_source)
        self.assertIn("isSigned()", right_shift_source)
        self.assertIn("getWidth() != 64", right_shift_source)

    def test_source_requires_a_constant_count_in_the_closed_zero_to_sixty_two_range(self) -> None:
        source = implementation_source()
        self.assertIn("ConstantIntOp", source)
        self.assertIn("shift_contract:dynamic_shift", source)
        self.assertIn("shift_contract:negative_shift", source)
        self.assertIn("shift_contract:greater_than_sixty_two", source)
        self.assertIn("62", source)

    def test_source_broadcasts_the_scalar_and_uses_arithmetic_right_shift(self) -> None:
        source = implementation_source()
        self.assertIn("AtenBroadcastToOp", source)
        self.assertIn("AtenBitwiseRightShiftTensorOp", source)
        self.assertIn("arith::ShRSIOp", source)
        self.assertNotIn("AtenDiv", source)

    def test_source_fails_closed_for_unsupported_dtype_or_count(self) -> None:
        source = implementation_source()
        self.assertIn("shift_contract:unsupported_dtype", source)
        self.assertIn("emitError", source)
        self.assertIn("signalPassFailure", source)

    def test_packaged_pipeline_generates_arithmetic_right_shift_ir(self) -> None:
        pipeline = (
            "builtin.module(func.func(torch-match-quantized-custom-ops), "
            "torchdynamo-export-to-torch-backend-pipeline{ extra-library=}, "
            "torch-backend-to-linalg-on-tensors-backend-pipeline)"
        )
        result = self.run_module(RIGHT_SHIFT_REPRODUCER.read_text(encoding="utf-8"), pipeline)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.output_created)
        self.assertTrue(result.output_text)
        self.assertIn("arith.shrsi", result.output_text)
        self.assertNotIn("torch.aten.bitwise_right_shift.Tensor_Scalar", result.output_text)

    def test_invalid_right_shift_inputs_emit_no_output(self) -> None:
        pipeline = (
            "builtin.module(func.func(torch-match-quantized-custom-ops), "
            "torchdynamo-export-to-torch-backend-pipeline{ extra-library=})"
        )
        dynamic = """module {
  func.func @main(%arg0: !torch.vtensor<[1],si64>, %count: !torch.int) -> !torch.vtensor<[1],si64> {
    %0 = torch.operator "torch.aten.bitwise_right_shift.Tensor_Scalar"(%arg0, %count) : (!torch.vtensor<[1],si64>, !torch.int) -> !torch.vtensor<[1],si64>
    return %0 : !torch.vtensor<[1],si64>
  }
}
"""
        cases = (
            (
                right_shift_module_text(count_definition="%count = torch.constant.int -1"),
                "shift_contract:negative_shift",
            ),
            (
                right_shift_module_text(count_definition="%count = torch.constant.int 63"),
                "shift_contract:greater_than_sixty_two",
            ),
            (dynamic, "shift_contract:dynamic_shift"),
            (
                right_shift_module_text(
                    input_type="!torch.vtensor<[1],si32>",
                    result_type="!torch.vtensor<[1],si32>",
                ),
                "shift_contract:unsupported_dtype",
            ),
        )
        for text, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic):
                self.assert_rejected_without_output(self.run_module(text, pipeline), diagnostic)

    def test_successor_reproducer_preserves_exact_left_shift_operation_and_types(self) -> None:
        self.assertTrue(LEFT_SHIFT_REPRODUCER.is_file())
        text = LEFT_SHIFT_REPRODUCER.read_text(encoding="utf-8")

        self.assertEqual(text.count("torch.operator"), 1)
        self.assertIn('torch.aten.bitwise_left_shift.Tensor_Scalar', text)
        self.assertIn(
            "(!torch.vtensor<[4,64],si64>, !torch.int) -> "
            "!torch.vtensor<[4,64],si64>",
            text,
        )


if __name__ == "__main__":
    unittest.main()
