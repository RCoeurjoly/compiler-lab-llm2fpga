import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tools/mlir-passes/FoldConstantTruncFOps.cpp").read_text()

class FixedLayerNormPluginRegistrationTest(unittest.TestCase):
    def test_pass_and_external_symbol_are_registered(self):
        self.assertIn('llm2fpga-lower-fixed-layernorm-q16', SOURCE)
        self.assertIn('llm2fpga.fixed_layer_norm_q16_16', SOURCE)
        self.assertIn('llm2fpga_fixed_layer_norm_q16_16', SOURCE)
        self.assertIn('PassRegistration<LowerFixedLayerNormQ16Pass>()', SOURCE)

if __name__ == '__main__': unittest.main()
