import json, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class OneBlockCompositionContractTest(unittest.TestCase):
    def test_contract_lists_all_transformer_stages_and_fails_closed(self):
        path = ROOT / 'artifacts/comparison/tinystories-1m-one-block-composition-contract-2026-08-29.json'
        doc = json.loads(path.read_text())
        names = [stage['name'] for stage in doc['stages']]
        for required in ('ln_1', 'q_projection', 'k_projection', 'v_projection', 'attention_softmax', 'attention_output', 'attention_residual', 'ln_2', 'mlp_fc_in', 'mlp_activation', 'mlp_fc_out', 'block_residual'):
            self.assertIn(required, names)
        self.assertTrue(doc['claims']['complete_block'])
        self.assertTrue(doc['claims']['functional_equivalence'])
        self.assertEqual(doc['transport']['ddr3'], 'unchanged')

if __name__ == '__main__': unittest.main()
