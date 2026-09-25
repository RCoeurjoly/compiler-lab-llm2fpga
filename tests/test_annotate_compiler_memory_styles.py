import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/annotate_compiler_memory_styles.py"
SPEC = importlib.util.spec_from_file_location("annotate_memory_styles", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AnnotateCompilerMemoryStylesTest(unittest.TestCase):
    def test_shallow_shapes_are_padded_and_not_forced_to_block(self):
        source = """
seq_mem_d1 # (.IDX_SIZE(4), .SIZE(8), .WIDTH(32)) mem_1 (
);
seq_mem_d1 # (.IDX_SIZE(1), .SIZE(1), .WIDTH(8)) mem_2 (
);
seq_mem_d1 # (.IDX_SIZE(3), .SIZE(4), .WIDTH(64)) mem_3 (
);
"""
        output, receipt = MODULE.annotate(source)
        self.assertNotIn('ram_style = "block"', output)
        self.assertEqual(receipt["counts"]["instances"], 3)
        self.assertEqual(receipt["counts"]["bram_annotations"], 0)
        self.assertEqual(receipt["counts"]["left_unconstrained"], 3)

    def test_single_entry_memory_is_scalarized_without_abi_change(self):
        source = """
seq_mem_d1 # (.IDX_SIZE(1), .SIZE(1), .WIDTH(8)) mem_2 (
  .addr0(a), .clk(c), .content_en(en), .done(done), .read_data(rd),
  .reset(r), .write_data(wd), .write_en(we)
);
"""
        output, receipt = MODULE.annotate(source)
        self.assertTrue(output.startswith("\nmodule seq_mem_d1_scalar"))
        self.assertIn("seq_mem_d1_scalar # (.IDX_SIZE(1), .SIZE(1), .WIDTH(8)) mem_2", output)
        self.assertEqual(receipt["scalar_size1_repairs"], 1)

    def test_shallow_memory_is_padded_to_lutram_geometry(self):
        source = """
seq_mem_d1 # (.IDX_SIZE(4), .SIZE(16), .WIDTH(32)) mem_7 (
);
"""
        output, receipt = MODULE.annotate(source)
        self.assertIn(".IDX_SIZE(5), .SIZE(32), .WIDTH(32)", output)
        self.assertEqual(receipt["padded_shallow_repairs"], 1)

    def test_non_memory_text_is_unchanged(self):
        source = "module main; logic x; endmodule\n"
        output, receipt = MODULE.annotate(source)
        self.assertEqual(output, source)
        self.assertEqual(receipt["counts"]["instances"], 0)


if __name__ == "__main__":
    unittest.main()
