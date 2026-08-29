import unittest
from pathlib import Path

from scripts.comparison.lower_softmax_packed_calyx import lower


class PackedSoftmaxCalyxTests(unittest.TestCase):
    def test_emits_external_primitive_component(self):
        source = 'module attributes {llm2fpga.bridge_manifest = {x = "y"}} {\n  func.func @tinystories_1m_attention_softmax(%scores: i16384, %position: i32) -> i16384 { return %scores : i16384 }\n}'
        result = lower(source)
        self.assertIn("hw.module.extern @llm2fpga_attention_softmax_fixed_tensor", result)
        self.assertIn("calyx.primitive @prim of @llm2fpga_attention_softmax_fixed_tensor", result)
        self.assertIn("calyx.component @tinystories_1m_attention_softmax", result)
        self.assertIn("{toplevel}", result)
        self.assertIn("%prim.clk, %prim.rst, %prim.start", result)

    def test_declared_ports_match_rtl_contract(self):
        rtl = Path("rtl/llm2fpga_attention_softmax_fixed_tensor.sv").read_text()
        for port in ("clk", "rst", "start", "position", "scores", "done", "busy", "probabilities"):
            self.assertIn(port, rtl)
        source = 'module {llm2fpga.bridge_manifest = {x = "y"}} {\n  func.func @f(%scores: i16384, %position: i32) -> i16384 { return %scores : i16384 }\n}'
        result = lower(source)
        for port in ("clk", "rst", "start", "position", "scores", "done", "busy", "probabilities"):
            self.assertIn(port, result)


if __name__ == "__main__":
    unittest.main()
