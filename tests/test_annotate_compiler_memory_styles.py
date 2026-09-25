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
    def test_only_legal_sized_shapes_are_forced_to_block(self):
        source = """
seq_mem_d1 # (.IDX_SIZE(4), .SIZE(8), .WIDTH(32)) mem_1 (
);
seq_mem_d1 # (.IDX_SIZE(1), .SIZE(1), .WIDTH(8)) mem_2 (
);
seq_mem_d1 # (.IDX_SIZE(3), .SIZE(4), .WIDTH(64)) mem_3 (
);
"""
        output, receipt = MODULE.annotate(source)
        self.assertIn('ram_style = "block" *) seq_mem_d1', output)
        self.assertEqual(output.count('ram_style = "block"'), 1)
        self.assertEqual(receipt["counts"]["instances"], 3)
        self.assertEqual(receipt["counts"]["bram_annotations"], 1)
        self.assertEqual(receipt["counts"]["left_unconstrained"], 2)

    def test_non_memory_text_is_unchanged(self):
        source = "module main; logic x; endmodule\n"
        output, receipt = MODULE.annotate(source)
        self.assertEqual(output, source)
        self.assertEqual(receipt["counts"]["instances"], 0)


if __name__ == "__main__":
    unittest.main()
