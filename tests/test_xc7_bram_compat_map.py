import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts/pipeline/make_xc7_bram_compat_map.py"
    spec = importlib.util.spec_from_file_location("xc7_bram_compat", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Xc7BramCompatMapTest(unittest.TestCase):
    def test_transforms_memory_libmap_parameter_abi(self):
        module = load_module()
        source = """module $__XILINX_BLOCKRAM_TDP_ (...);
parameter PORT_A_RD_WIDTH = 1;
parameter PORT_A_RD_USED = 1;
parameter PORT_B_RD_WIDTH = 1;
parameter PORT_B_RD_USED = 0;
endmodule
"""
        output, receipt = module.transform(source)
        self.assertIn("parameter PORT_A_WIDTH = 1;", output)
        self.assertIn("parameter PORT_A_USED = 1;", output)
        self.assertNotIn("PORT_A_RD_WIDTH", output)
        self.assertNotIn("PORT_A_RD_USED", output)
        self.assertEqual(receipt["replacement_count"], 4)

    def test_transform_is_idempotent(self):
        module = load_module()
        source = "module $__XILINX_BLOCKRAM_TDP_ (...); endmodule\n"
        output, first = module.transform(source)
        second_output, second = module.transform(output)
        self.assertEqual(second_output, output)
        self.assertEqual(first["replacement_count"], 0)
        self.assertEqual(second["replacement_count"], 0)


if __name__ == "__main__":
    unittest.main()
