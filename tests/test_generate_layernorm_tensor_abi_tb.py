import importlib.util, json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gen_ln', ROOT / 'scripts/comparison/generate_layernorm_tensor_abi_tb.py')
mod = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)

class GenerateLayerNormTensorTbTest(unittest.TestCase):
    def test_generates_all_64_output_checks(self):
        ref = json.loads((ROOT / 'artifacts/reference/tinystories-1m-rtl-layernorm-vector.json').read_text())
        tb = mod.generate(ref)
        self.assertEqual(tb.count('lane '), 64)
        self.assertIn('GPTNEO_LAYERNORM_TENSOR_ABI_PASS', tb)

if __name__ == '__main__': unittest.main()
