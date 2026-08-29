import importlib.util, json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/generate_softmax_tensor_abi_tb.py"
spec = importlib.util.spec_from_file_location("tensor_gen", SCRIPT)
mod = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)

class GenerateSoftmaxTensorAbiTbTest(unittest.TestCase):
    def test_covers_all_rows_and_packed_lanes(self):
        ref = json.loads((ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json").read_text())
        tb = mod.generate(ref)
        self.assertEqual(tb.count("upper bits nonzero"), 16 * 4)
        self.assertIn("GPTNEO_SOFTMAX_TENSOR_ABI_16_ROWS_PASS", tb)
        self.assertIn("probabilities[0 +: 21]", tb)

if __name__ == "__main__": unittest.main()
