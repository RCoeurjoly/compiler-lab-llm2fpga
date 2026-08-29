import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ValidateOneBlockTraceTest(unittest.TestCase):
    def test_ordered_trace_is_complete_but_not_overclaimed(self):
        p=ROOT/'artifacts/comparison/tinystories-1m-one-block-trace-validation-2026-08-29.json'; d=json.loads(p.read_text())
        self.assertEqual(len(d['checkpoint_order']),12); self.assertTrue(d['claims']['ordered_checkpoint_hashes']); self.assertFalse(d['claims']['rtl_composed'])
if __name__=='__main__': unittest.main()
