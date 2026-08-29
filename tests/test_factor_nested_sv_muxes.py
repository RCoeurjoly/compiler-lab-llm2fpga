import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/factor_nested_sv_muxes.py"


def load_module():
    spec = importlib.util.spec_from_file_location("factor_nested_sv_muxes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FactorNestedSvMuxesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_factors_top_level_nested_ternary_and_preserves_lhs(self):
        source = """module m(input logic a, b, c, input logic [31:0] x, y, z, output logic [31:0] q);
logic [31:0] n;
assign n = a ? x : b ? y : c ? z : 32'd0;
endmodule
"""
        output, receipt = self.module.factor(source)
        self.assertIn("assign n =", output)
        self.assertGreaterEqual(receipt["factor_count"], 2)
        self.assertNotIn("assign n = a ? x : b ?", output)
        self.assertIn("wire [31:0]", output)

    def test_unbalanced_expression_is_left_unchanged(self):
        source = "module m(input logic a, output logic q); assign q = a; endmodule\n"
        output, receipt = self.module.factor(source)
        self.assertEqual(output, source)
        self.assertEqual(receipt["factor_count"], 0)


if __name__ == "__main__":
    unittest.main()
