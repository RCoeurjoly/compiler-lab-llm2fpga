import unittest
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CalyxMathLegalizationTest(unittest.TestCase):
    def test_roundeven_lowering_preserves_negative_infinity(self) -> None:
        mlir_opt = os.environ.get("MLIR_OPT") or shutil.which("mlir-opt")
        pass_plugin = os.environ.get("LLM2FPGA_MLIR_PASS_PLUGIN")
        if not mlir_opt or not pass_plugin:
            self.skipTest("set MLIR_OPT and LLM2FPGA_MLIR_PASS_PLUGIN")

        fixture = ROOT / "reproducers" / "calyx-math-roundeven" / "nonfinite.mlir"
        completed = subprocess.run(
            [
                mlir_opt,
                f"--load-pass-plugin={pass_plugin}",
                "--pass-pipeline=builtin.module(llm2fpga-lower-roundeven-for-calyx,canonicalize)",
                str(fixture),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("0xFF800000 : f32", completed.stdout)
        self.assertNotIn("arith.fptosi", completed.stdout)

    def test_pre_calyx_pipeline_legalizes_exact_supported_math(self) -> None:
        pipeline = (ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        source = (
            ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpga-lower-exact-math-for-calyx", pipeline)
        self.assertIn("PassRegistration<LowerExactMathForCalyxPass>", source)
        self.assertIn("math::FloorOp", source)
        self.assertIn("math::CeilOp", source)
        self.assertIn("math::RsqrtOp", source)
        self.assertIn("math::AbsIOp", source)
        self.assertIn("math::SqrtOp::create", source)

    def test_scout_approximations_are_explicit_and_opt_in(self) -> None:
        pipeline = (ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        source = (
            ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpga-lower-scout-math-for-calyx", pipeline)
        self.assertIn('name == "tinystories-w8a8"', pipeline)
        self.assertIn("PassRegistration<LowerScoutMathForCalyxPass>", source)
        self.assertIn("math::ExpOp", source)
        self.assertIn("math::PowFOp", source)
        self.assertIn("math::TanhOp", source)
        self.assertIn("resource scout", source.lower())

    def test_polynomial_exp_candidate_is_registered_but_not_canonical(self) -> None:
        pipeline = (ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        source = (
            ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpga-lower-polynomial-exp-for-calyx", source)
        self.assertIn("PassRegistration<LowerPolynomialExpForCalyxPass>", source)
        self.assertIn("fifth-order Taylor candidate", source)
        self.assertNotIn("llm2fpga-lower-polynomial-exp-for-calyx", pipeline)

    def test_constant_fpowi_candidate_is_explicitly_opt_in(self) -> None:
        pipeline = (ROOT / "flake.nix").read_text(encoding="utf-8")
        source = (
            ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpga-lower-constant-fpowi-for-calyx", pipeline)
        self.assertIn("PassRegistration<LowerConstantFPowIForCalyxPass>", source)
        self.assertIn("math::FPowIOp", source)

    def test_rational_tanh_candidate_is_explicitly_opt_in(self) -> None:
        pipeline = (ROOT / "flake.nix").read_text(encoding="utf-8")
        source = (
            ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpga-lower-rational-tanh-for-calyx", pipeline)
        self.assertIn("PassRegistration<LowerRationalTanhForCalyxPass>", source)
        self.assertIn("gated rational candidate", source)

    def test_scalar_f32_negf_legalization_is_registered(self) -> None:
        source = (
            ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpga-lower-negf-for-calyx", source)
        self.assertIn("PassRegistration<LowerNegFForCalyxPass>", source)


if __name__ == "__main__":
    unittest.main()
