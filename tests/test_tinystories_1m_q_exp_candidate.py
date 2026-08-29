"""Tests for the fail-closed TinyStories-1M q_exp candidate probe."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/evaluate_tinystories_1m_q_exp_candidate.py"
REPORT = ROOT / "artifacts/comparison/tinystories-1m-q-exp-candidate.json"


def load_module():
    spec = importlib.util.spec_from_file_location("q_exp_candidate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QExpCandidateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_report_is_content_bound_and_fail_closed(self):
        unsigned = {key: value for key, value in self.report.items() if key != "sha256"}
        self.assertEqual(self.report["schema"], "tinystories-1m-q-exp-candidate-evaluation-v1")
        self.assertEqual(self.report["sha256"], self.module.canonical_sha256(unsigned))
        self.assertEqual(self.report["status"], "unsupported")
        self.assertFalse(self.report["claims"]["full_attention_row_error"])
        self.assertFalse(self.report["decision"]["accepted"])

    def test_rtl_candidate_is_bound_and_saturates(self):
        self.assertEqual(self.report["candidate"]["rtl_sha256"], self.module.sha256_file(self.module.RTL))
        self.assertEqual(self.module.q_exp_approx(-8.0)[1], 0)
        self.assertEqual(self.module.q_exp_approx(8.0)[1], self.module.I32_MAX)
        self.assertEqual(self.module.q_exp_approx(0.0)[1], self.module.Q)
        self.assertEqual(self.module.q16_16_to_f32_bits(self.module.I32_MAX), 0x46FFFFFF)
        self.assertEqual(self.module.q16_16_to_f32_bits(-self.module.I32_MAX), 0xC6FFFFFF)

    def test_package_tamper_is_rejected(self):
        package = Path("/tmp/kev-gpt-startinit/model_packages/tinystories-1m")
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "package"
            shutil.copytree(package, copy)
            (copy / "weights.bin").write_bytes((copy / "weights.bin").read_bytes()[:1] + b"tampered")
            with self.assertRaisesRegex(ValueError, "package hash mismatch"):
                self.module.package_evidence(copy)

    def test_q_exp_conversion_truncates_not_rounds(self):
        # INT32_MAX is the high saturation result in RTL; IEEE conversion of
        # q/Q would round to 32768.0, while RTL emits the truncated 32767.999...
        self.assertEqual(self.module.q16_16_to_f32_bits(self.module.I32_MAX), 0x46FFFFFF)

    def test_qdq_receipt_does_not_claim_complete_score_rows(self):
        boundary = self.report["qdq_boundary"]
        self.assertEqual(boundary["q_checkpoint_shape"], [16, 4])
        self.assertEqual(boundary["k_checkpoint_shape"], [16, 4])
        self.assertEqual(boundary["qdq_receipt_schema"], "tinystories-1m-qdq-semantics-v1")
        self.assertEqual(boundary["qdq_receipt_self_sha256"], "c025c8e89ba71dca2437b89f90105d9cc5fd44366e5b51ef089288d15fde730f")
        self.assertFalse(boundary["complete_causal_score_rows_available"])
        self.assertEqual(boundary["comparison_status"], "unsupported")

    def test_characterization_is_nontrivial(self):
        summary = self.report["candidate_characterization"]
        stabilized = summary["stabilized_domain"]
        extended = summary["extended_probe"]
        self.assertGreater(stabilized["sample_count"], 65500)
        self.assertGreater(stabilized["max_absolute_error"], 0.0)
        self.assertEqual(stabilized["domain"]["min"], -8.0)
        self.assertEqual(stabilized["domain"]["max"], 0.0)
        self.assertEqual(extended["domain"]["min"], -8.5)
        self.assertEqual(extended["domain"]["max"], 8.5)


if __name__ == "__main__":
    unittest.main()
