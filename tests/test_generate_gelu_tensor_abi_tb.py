import importlib.util, json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gen_gelu', ROOT / 'scripts/comparison/generate_gelu_tensor_abi_tb.py')
mod = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)

class GenerateGeluTensorTbTest(unittest.TestCase):
    def test_generates_256_lane_checks_and_lut(self):
        ref = json.loads((ROOT / 'artifacts/reference/tinystories-1m-candidate-oracle.json').read_text())
        tb = mod.generate(ref)
        self.assertEqual(tb.count('lane '), 256)
        self.assertIn('LLM2FPGA_GELU_TENSOR_PASS', tb)
        self.assertEqual(len(mod.lut_lines().splitlines()), 8192)

if __name__ == '__main__': unittest.main()
