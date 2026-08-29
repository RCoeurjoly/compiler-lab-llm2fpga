import importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("gen",ROOT/"scripts/comparison/generate_softmax_only_tb.py"); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
class GenerateSoftmaxTbTest(unittest.TestCase):
    def test_generates_all_authenticated_rows(self):
        ref=json.loads((ROOT/"artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json").read_text()); tb=mod.generate(ref)
        self.assertEqual(tb.count("position<=3"),16); self.assertIn("GPTNEO_SOFTMAX_ONLY_16_ROWS_PASS",tb)
if __name__ == "__main__": unittest.main()
