import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GemvAdapterReceiptTest(unittest.TestCase):
    def test_receipt_records_hidden_and_mlp_shapes(self):
        d=json.loads((ROOT/'artifacts/comparison/tinystories-1m-gemv-rtl-adapter-2026-08-29.json').read_text())
        self.assertEqual(d['status'],'hidden_shape_simulation_and_mlp_shape_elaboration_pass')
        self.assertTrue(d['claims']['hidden_projection_shape_simulated'])
        self.assertTrue(d['claims']['both_mlp_projection_shapes_elaborated'])
if __name__=='__main__': unittest.main()
