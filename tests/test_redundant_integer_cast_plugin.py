import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tools/mlir-passes/FoldConstantTruncFOps.cpp").read_text()
FIXTURE = (ROOT / "tests/fixtures/redundant_integer_casts.mlir").read_text()


class RedundantIntegerCastPluginTest(unittest.TestCase):
    def test_pass_is_registered_and_width_guarded(self):
        self.assertIn("llm2fpga-fold-redundant-integer-casts", SOURCE)
        self.assertIn("PassRegistration<FoldRedundantIntegerCastsPass>", SOURCE)
        self.assertIn("sourceInt.getWidth() != resultInt.getWidth()", SOURCE)
        self.assertIn("llm2fpga-fold-identity-integer-arithmetic", SOURCE)
        self.assertIn("PassRegistration<FoldIdentityIntegerArithmeticPass>", SOURCE)

    def test_fixture_contains_safe_and_unsafe_pairs(self):
        self.assertIn("arith.extsi %arg0 : i32 to i64", FIXTURE)
        self.assertIn("arith.trunci %a : i64 to i32", FIXTURE)
        self.assertIn("arith.trunci %e : i32 to i16", FIXTURE)


if __name__ == "__main__":
    unittest.main()
