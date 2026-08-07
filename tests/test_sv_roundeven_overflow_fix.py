import unittest

from scripts.pipeline.fix_sv_roundeven_overflow import rewrite


class SvRoundEvenOverflowFixTest(unittest.TestCase):
    def test_only_std_add_is_repaired(self) -> None:
        source = """\
module std_fp_add #(parameter WIDTH = 32) (input logic [WIDTH-1:0] left, right,
  output logic [WIDTH-1:0] out);
assign out = left + right;
endmodule
module std_add #(parameter WIDTH = 32) (input logic [WIDTH-1:0] left, right,
  output logic [WIDTH-1:0] out);
assign out = left + right;
endmodule
"""
        updated, count = rewrite(source)
        self.assertEqual(count, 1)
        self.assertIn("left == 32'h80000000", updated)
        self.assertIn("module std_fp_add", updated)
        self.assertEqual(updated.count("assign out = left + right;"), 1)

    def test_rejects_missing_std_add(self) -> None:
        with self.assertRaises(ValueError):
            rewrite("module std_fp_add; assign out = left + right; endmodule")


if __name__ == "__main__":
    unittest.main()
