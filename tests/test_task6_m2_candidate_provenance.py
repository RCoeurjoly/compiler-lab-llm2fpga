"""The production M2 candidate receipt binds tracked inputs and exact proof."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "artifacts/reference/compiler-ddr3-trace-replay-m2-candidate-provenance.json"


class M2CandidateProvenanceTest(unittest.TestCase):
    def test_receipt_authenticates_tracked_inputs_profile_and_canonical_proof(self):
        self.assertTrue(RECEIPT.is_file(), "production M2 provenance receipt is missing")
        receipt = json.loads(RECEIPT.read_text())
        self.assertEqual(receipt["schema"], "compiler-ddr3-trace-replay-m2-candidate-v1")
        self.assertEqual(receipt["status"], "canonical-netlist-identity-proven")
        for path, expected in receipt["tracked_inputs"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected, path)
        self.assertEqual(receipt["transform"]["input_sha256"],
                         "224b3a384770378a64768aaa900adcba07a3672812dd92d3b70fadf6a88315f1")
        self.assertEqual(receipt["transform"]["output_sha256"],
                         "d3974d466d6e13c895d888d09fb63d8725a15be72756736dae948d30b4b3acea")
        proof = receipt["netlist_proof"]
        self.assertEqual(proof["reference_raw_sha256"],
                         "553769872b35ec28a8aa60a83973bdccb1c860507b060816b96ce04ab0adf74f")
        self.assertEqual(proof["production_raw_sha256"],
                         "f24399228ba1009fbf1c890c01bfc670c140919479ca5df5d82c41c2c3c40e22")
        self.assertEqual(proof["canonical_sha256"],
                         "d7b3ec7cddb4d08caa270838d208e62879a51b1fdcb3cd14582a8c34c6d30009")
        self.assertEqual(proof["difference_classes"], {
            "ordering": 0, "source_path_keys": 76,
            "source_path_values": 16116,
            "metadata_values": {
                "src": 16023, "module_src": 46, "cell_src": 43,
                "generated_function_hdlname": 4},
            "generated_keys": {"cells": 1, "netnames": 75},
            "unexplained": 0})
        self.assertEqual(len(receipt["sources"]), 36)
        self.assertTrue(all(len(row["sha256"]) == 64 for row in receipt["sources"]))
        self.assertEqual(receipt["profile"]["seed"], 15)
        self.assertEqual(receipt["profile"]["byte_lanes"], 2)
        self.assertEqual(receipt["profile"]["bist_mode"], 2)
        self.assertEqual(receipt["profile"]["controller_period_ps"], 12000)
        self.assertEqual(receipt["profile"]["ddr_period_ps"], 3000)
        self.assertFalse(receipt["scope"]["route_performed"])
        self.assertFalse(receipt["scope"]["bitstream_generated"])
        self.assertGreaterEqual(len(receipt["timing_coverage_limitations"]), 6)


if __name__ == "__main__":
    unittest.main()
