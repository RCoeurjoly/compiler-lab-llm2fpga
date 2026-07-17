import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/run_rc_sv_equivalence.py"
spec = importlib.util.spec_from_file_location("run_rc_sv_equivalence", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RcSvEquivalenceFixtureTest(unittest.TestCase):
    def test_calyx_memory_ports_are_parsed(self):
        source = """
        module main_1(
          input logic clk, output logic [2:0] arg_mem_25_addr0,
          output logic arg_mem_25_content_en, output logic arg_mem_25_write_en,
          output logic [63:0] arg_mem_25_write_data,
          input logic [63:0] arg_mem_25_read_data, input logic arg_mem_25_done,
          output logic [5:0] arg_mem_26_addr0,
          output logic [7:0] arg_mem_26_write_data,
          input logic [7:0] arg_mem_26_read_data, input logic arg_mem_26_done);
        endmodule
        """
        ports = module._ports(source)
        self.assertEqual(ports[25], (64, 8))
        self.assertEqual(ports[26], (8, 64))

    def test_fixture_requires_functional_buffers(self):
        with self.assertRaises(RuntimeError):
            module._fixture("module main(input logic clk); endmodule", b"", {"segments": []}, {}, Path("/tmp"))


if __name__ == "__main__":
    unittest.main()
