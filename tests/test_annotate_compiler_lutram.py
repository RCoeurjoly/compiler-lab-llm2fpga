import unittest

from scripts.pipeline.annotate_compiler_lutram import annotate


class CompilerLutramAnnotationTests(unittest.TestCase):
    def test_only_lutram_primitive_gets_attribute(self):
        source = """
module seq_mem_d1 #(parameter WIDTH=8, parameter SIZE=4);
  logic [WIDTH-1:0] mem[SIZE-1:0];
endmodule
module seq_mem_d1_lutram #(parameter WIDTH=8, parameter SIZE=4);
  logic [WIDTH-1:0] mem[SIZE-1:0];
endmodule
"""
        result, changed = annotate(source)
        self.assertTrue(changed)
        self.assertEqual(result.count('ram_style = "distributed"'), 1)
        self.assertEqual(result.count("logic [WIDTH-1:0] mem[SIZE-1:0];"), 2)

    def test_annotation_is_idempotent(self):
        source = """
module seq_mem_d1_lutram #(parameter WIDTH=8);
  (* ram_style = "distributed" *)
  logic [WIDTH-1:0] mem[3:0];
endmodule
"""
        result, changed = annotate(source)
        self.assertFalse(changed)
        self.assertEqual(result, source)


if __name__ == "__main__":
    unittest.main()
