import json, unittest
from pathlib import Path
class MlpCompositionReceiptTest(unittest.TestCase):
    def test_real_vector_pass_is_scoped(self):
        p=Path(__file__).resolve().parents[1]/'artifacts/comparison/tinystories-1m-mlp-composition-equivalence-2026-08-29.json'; d=json.loads(p.read_text())
        self.assertEqual(d['status'],'real_vector_simulation_pass'); self.assertTrue(d['claims']['mlp_residual_functional_equivalence']); self.assertFalse(d['claims']['complete_attention_block_equivalence'])
if __name__=='__main__': unittest.main()
