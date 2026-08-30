from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "TinyStories/model_adapter_exact_package.py"
EXPECTED_ADAPTER_SHA256 = (
    "d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e"
)
PATCH = ROOT / "patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch"
PLUGIN = ROOT / "tools/torch-mlir-passes/LegalizeBitwiseRightShiftTensorScalar.cpp"


def implementation_source() -> str:
    implementations = [path for path in (PATCH, PLUGIN) if path.is_file()]
    if len(implementations) != 1:
        raise AssertionError(
            "expected exactly one Tensor_Scalar shift legalization implementation, "
            f"found {implementations}"
        )
    return implementations[0].read_text(encoding="utf-8")


class TinyStories1mExactShiftLegalizationTest(unittest.TestCase):
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
        self.assertIn("torch.aten.bitwise_right_shift.Tensor_Scalar", source)
        self.assertIn("ValueTensorType", source)
        self.assertIn("isSigned()", source)
        self.assertIn("getWidth() != 64", source)

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


if __name__ == "__main__":
    unittest.main()
