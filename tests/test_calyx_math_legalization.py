import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CalyxMathLegalizationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
