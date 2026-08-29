import json, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class CandidateOracleArtifactTest(unittest.TestCase):
    def test_has_all_ordered_block_checkpoints_and_is_not_board_claim(self):
        doc = json.loads((ROOT / 'artifacts/reference/tinystories-1m-candidate-oracle.json').read_text())
        self.assertEqual(doc['schema'], 'tinystories-1m-candidate-oracle-v1')
        self.assertEqual(len(doc['oracle']['checkpoint_order']), 12)
        self.assertEqual(set(doc['oracle']['checkpoint_order']), set(doc['oracle']['checkpoints']))
        self.assertFalse(doc['claims']['board_authenticated'])

if __name__ == '__main__': unittest.main()
