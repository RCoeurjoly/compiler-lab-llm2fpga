import importlib.util, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('abi', ROOT / 'scripts/comparison/verify_tinystories_1m_external_abi.py')
abi = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(abi)

class ExternalAbiVerifierTest(unittest.TestCase):
    def test_current_adapters_are_named_and_parseable(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            sm = d / 'sm.mlir'; ln = d / 'ln.mlir'
            sm.write_text('call @llm2fpga_attention_softmax_fixed : (tensor<16x32xi32>, i32) -> tensor<16x32xi32>')
            ln.write_text('call @llm2fpga_fixed_layer_norm_q16_16 : (tensor<64xi32>, tensor<64xi32>, tensor<64xi32>) -> tensor<64xi32>')
            result = abi.verify(sm, ln, ROOT / 'rtl/llm2fpga_attention_softmax_fixed_tensor.sv', ROOT / 'rtl/llm2fpga_fixed_layer_norm_q16_16_tensor.sv')
        self.assertTrue(result['claims']['call_signatures_match_packed_adapters'])

if __name__ == '__main__': unittest.main()
