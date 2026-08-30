from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch"
REPRODUCER = (
    ROOT
    / "reproducers"
    / "tinystories-1m-exact-torch-mlir"
    / "bitwise-left-shift-tensor-scalar.mlir"
)
BACKEND_PIPELINE = (
    "builtin.module(func.func(torch-match-quantized-custom-ops), "
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=})"
)
LINALG_PIPELINE = (
    "builtin.module(func.func(torch-match-quantized-custom-ops), "
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=}, "
    "torch-backend-to-linalg-on-tensors-backend-pipeline)"
)


def implementation_source() -> str:
    return PATCH.read_text(encoding="utf-8")


def module_text(
    *,
    input_type: str = "!torch.vtensor<[4,64],si64>",
    result_type: str = "!torch.vtensor<[4,64],si64>",
    count_definition: str = "%count = torch.constant.int 16",
) -> str:
    return f"""module {{
  func.func @main(%arg0: {input_type}) -> {result_type} {{
    {count_definition}
    %0 = torch.operator \"torch.aten.bitwise_left_shift.Tensor_Scalar\"(%arg0, %count) : ({input_type}, !torch.int) -> {result_type}
    return %0 : {result_type}
  }}
}}
"""


class TinyStories1mExactLeftShiftLegalizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tool = shutil.which("torch-mlir-opt")
        if cls.tool is None:
            raise AssertionError("test must run inside the pinned Nix environment")

    def run_module(self, text: str, pipeline: str = BACKEND_PIPELINE) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="exact-left-shift-runtime-") as temporary:
            source = Path(temporary) / "input.mlir"
            output = Path(temporary) / "output.mlir"
            source.write_text(text, encoding="utf-8")
            result = subprocess.run(
                [
                    str(self.tool),
                    f"-pass-pipeline={pipeline}",
                    str(source),
                    "-o",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            if result.returncode == 0:
                result.stdout = output.read_text(encoding="utf-8")
            return result

    def test_source_has_distinct_exact_left_shift_matcher(self) -> None:
        source = implementation_source()
        self.assertIn("LegalizeBitwiseLeftShiftTensorScalarPass", source)
        self.assertIn("torch.aten.bitwise_left_shift.Tensor_Scalar", source)
        self.assertIn("AtenBitwiseLeftShiftTensorOp", source)
        self.assertIn("inputType != resultType", source)
        self.assertIn("inputDtype.isSigned()", source)
        self.assertIn("inputDtype.getWidth() != 64", source)

    def test_source_materializes_and_broadcasts_the_scalar(self) -> None:
        source = implementation_source()
        self.assertIn("createRank0Tensor", source)
        self.assertIn("AtenBroadcastToOp", source)

    def test_valid_direct_counts_lower_to_registered_tensor_left_shift(self) -> None:
        for count in (0, 16, 62):
            with self.subTest(count=count):
                result = self.run_module(
                    module_text(count_definition=f"%count = torch.constant.int {count}")
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("torch.aten.bitwise_left_shift.Tensor", result.stdout)
                self.assertNotIn("torch.aten.bitwise_left_shift.Tensor_Scalar", result.stdout)

    def test_generated_linalg_uses_integer_left_shift(self) -> None:
        result = self.run_module(REPRODUCER.read_text(encoding="utf-8"), LINALG_PIPELINE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("arith.shli", result.stdout)
        self.assertNotIn("torch.aten.bitwise_left_shift.Tensor_Scalar", result.stdout)
        self.assertNotIn("arith.shrsi", result.stdout)

    def test_negative_count_is_rejected_with_exact_diagnostic(self) -> None:
        result = self.run_module(module_text(count_definition="%count = torch.constant.int -1"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shift_contract:negative_shift", result.stderr)

    def test_count_sixty_three_is_rejected_with_exact_diagnostic(self) -> None:
        result = self.run_module(module_text(count_definition="%count = torch.constant.int 63"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shift_contract:greater_than_sixty_two", result.stderr)

    def test_dynamic_count_is_rejected_with_exact_diagnostic(self) -> None:
        dynamic = """module {
  func.func @main(%arg0: !torch.vtensor<[1],si64>, %count: !torch.int) -> !torch.vtensor<[1],si64> {
    %0 = torch.operator "torch.aten.bitwise_left_shift.Tensor_Scalar"(%arg0, %count) : (!torch.vtensor<[1],si64>, !torch.int) -> !torch.vtensor<[1],si64>
    return %0 : !torch.vtensor<[1],si64>
  }
}
"""
        result = self.run_module(dynamic)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shift_contract:dynamic_shift", result.stderr)

    def test_si32_input_is_rejected_with_exact_diagnostic(self) -> None:
        result = self.run_module(
            module_text(
                input_type="!torch.vtensor<[1],si32>",
                result_type="!torch.vtensor<[1],si32>",
                count_definition="%count = torch.constant.int 1",
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shift_contract:unsupported_dtype", result.stderr)

    def test_mismatched_signed_si64_types_are_rejected(self) -> None:
        result = self.run_module(
            module_text(
                input_type="!torch.vtensor<[1],si64>",
                result_type="!torch.vtensor<[2],si64>",
                count_definition="%count = torch.constant.int 1",
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shift_contract:unsupported_dtype", result.stderr)


if __name__ == "__main__":
    unittest.main()
