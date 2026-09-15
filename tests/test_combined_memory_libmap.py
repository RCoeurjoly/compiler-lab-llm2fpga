import unittest

from scripts.pipeline.map_generated_memories import build_yosys_script


class CombinedMemoryLibmapTests(unittest.TestCase):
    def test_script_uses_bram_and_lutram_libraries_and_fails_closed(self):
        script = build_yosys_script("input.sv", "output.il", "main")
        self.assertIn("memory_libmap", script)
        self.assertIn("+/xilinx/brams_xc4v.txt", script)
        self.assertIn("+/xilinx/lutrams_xc5v.txt", script)
        self.assertIn("write_rtlil output.il", script)


if __name__ == "__main__":
    unittest.main()
