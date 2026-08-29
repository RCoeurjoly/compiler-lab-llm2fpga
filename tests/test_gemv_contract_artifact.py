import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GemvContractArtifactTest(unittest.TestCase):
    def test_contract_binds_serial_accumulator_and_shapes(self):
        d=json.loads((ROOT/'artifacts/reference/tinystories-1m-gemv-contract.json').read_text())
        self.assertTrue(d['claims']['fixed_gemv_semantics_authenticated'])
        self.assertEqual(d['contract']['accumulation']['synthesizable_rtl']['logical_width_bits'],64)
        self.assertEqual(d['matrix_shapes']['mlp_in']['output_width'],256)
        self.assertEqual(d['contract']['activation_conversion']['clamp'],[-128,127])
if __name__=='__main__': unittest.main()
