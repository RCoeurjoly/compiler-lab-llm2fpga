"""Tests for the supplementary, non-authoritative attention oracle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/build_tinystories_1m_attention_softmax_oracle.py"
REPORT = ROOT / "artifacts/comparison/tinystories-1m-attention-softmax-oracle.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path(
    "/home/roland/.cache/huggingface/hub/models--roneneldan--TinyStories-1M/"
    "snapshots/77f1b168e219585646439073245fe87e56b3023e"
)


def load_module():
    spec = importlib.util.spec_from_file_location("tinystories_attention_oracle", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AttentionOracleArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_report_is_content_bound_and_non_authoritative(self):
        self.assertEqual(self.report["schema"], "tinystories-1m-attention-softmax-software-oracle-v1")
        unsigned = {key: value for key, value in self.report.items() if key != "sha256"}
        self.assertEqual(self.report["sha256"], self.module.canonical_sha256(unsigned))
        self.assertEqual(self.report["status"], "supplementary_non_authoritative")
        self.assertFalse(any(self.report["authority"].values()))

    def test_complete_causal_rows_and_probability_normalization(self):
        trace = self.report["trace"]
        self.assertEqual(trace["sequence_length"], 4)
        self.assertEqual(trace["num_heads"], 16)
        self.assertEqual(trace["head_dim"], 4)
        for row in trace["rows"]:
            scores = row["score_rows"]
            probs = row["softmax_rows"]
            shifted = row["shifted_score_rows"]
            exponentials = row["exp_shifted_rows"]
            self.assertEqual(len(scores), 4)
            self.assertEqual(len(probs), 4)
            for query_index in range(4):
                self.assertEqual(len(scores[query_index]), 4)
                self.assertEqual(len(probs[query_index]), 4)
                self.assertAlmostEqual(sum(probs[query_index][: query_index + 1]), 1.0, places=6)
                self.assertTrue(all(value == 0.0 for value in probs[query_index][query_index + 1 :]))
                self.assertAlmostEqual(max(shifted[query_index][: query_index + 1]), 0.0, places=6)
                self.assertAlmostEqual(max(exponentials[query_index][: query_index + 1]), 1.0, places=6)
        # The first query has exactly one legal key; this catches reductions
        # that accidentally include future (masked) score columns.
        self.assertTrue(all(row["shifted_score_rows"][0] == [0.0, 0.0, 0.0, 0.0] for row in trace["rows"]))
        self.assertTrue(all(row["exp_shifted_rows"][0] == [1.0, 0.0, 0.0, 0.0] for row in trace["rows"]))

    def test_identity_binds_authenticated_inputs(self):
        identity = self.report["identity"]
        self.assertEqual(identity["contract_sha256"], self.module.sha256_file(self.module.CONTRACT))
        self.assertEqual(identity["package_manifest_sha256"], self.module.sha256_file(PACKAGE / "manifest.json"))
        self.assertEqual(identity["package_weights_sha256"], self.module.sha256_file(PACKAGE / "weights.bin"))
        self.assertEqual(identity["package_scales_sha256"], self.module.sha256_file(PACKAGE / "scales.bin"))
        self.assertEqual(identity["package_calibration_ids_sha256"], self.module.sha256_file(PACKAGE / "calibration_ids.bin"))
        self.assertEqual(identity["package_receipt_sha256"], self.module.sha256_file(PACKAGE / "receipt.json"))
        self.assertEqual(identity["adapter_sha256"], self.module.sha256_file(self.module.ADAPTER))

    def test_exp_domain_and_candidate_error_are_recorded(self):
        domains = self.report["trace"]["domains"]
        self.assertGreater(domains["causal_scores"]["count"], 0)
        self.assertGreaterEqual(domains["shifted_scores"]["max"], 0.0)
        self.assertGreater(domains["exp_shifted"]["min"], 0.0)
        candidate = self.report["trace"]["q_exp_candidate"]
        self.assertEqual(candidate["sample_count"], domains["exp_shifted"]["count"])
        self.assertGreaterEqual(candidate["max_absolute_error"], 0.0)
        self.assertIn("software-only", candidate["comparison"])

    @unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "authenticated package/model unavailable")
    def test_rebuilding_is_deterministic(self):
        rebuilt = self.module.build_report(self.module.CONTRACT, PACKAGE, MODEL, 0)
        self.assertEqual(rebuilt, self.report)

    def test_missing_inputs_fail_closed(self):
        with self.assertRaisesRegex(Exception, "missing|unavailable"):
            self.module.build_report(
                Path("/nonexistent/contract.json"),
                PACKAGE,
                MODEL,
                0,
            )


if __name__ == "__main__":
    unittest.main()
