from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/authenticate_tinystories_1m_layernorm_semantics.py"
REFERENCE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest")
QDQ = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
RECEIPT = ROOT / "artifacts/reference/tinystories-1m-layernorm-semantics.json"


def load_module():
    spec = importlib.util.spec_from_file_location("layernorm_semantics", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LayerNormSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_receipt_is_content_bound_and_fail_closed(self):
        receipt = json.loads(RECEIPT.read_text())
        self.assertEqual(receipt["status"], "incomplete")
        self.assertIsNone(receipt["selected_profile"])
        self.assertEqual(receipt["receipt_sha256"], self.module.receipt_sha256(receipt))
        self.assertIn("layernorm_overflow_domain_conflict", {item["code"] for item in receipt["conflicts"]})

    def test_rederive_matches_checked_in_receipt(self):
        expected = json.loads(RECEIPT.read_text())
        actual = self.module.derive_receipt(REFERENCE, QDQ)
        actual["receipt_sha256"] = self.module.receipt_sha256(actual)
        self.assertEqual(actual, expected)

    def test_tampered_qdq_profile_cannot_supply_trace_or_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile.json"
            profile.write_text(QDQ.read_text().replace('"profile": "fixed_hardware_reference"', '"profile": "tampered"', 1))
            with self.assertRaisesRegex(self.module.LayerNormEvidenceError, "qdq_profile_identity_mismatch"):
                self.module.derive_receipt(REFERENCE, profile)

    def test_runtime_and_rtl_width_difference_is_not_silently_selected(self):
        receipt = self.module.derive_receipt(REFERENCE, QDQ)
        runtime = receipt["candidate_profiles"]["fixed_hardware_runtime"]["reduction"]
        rtl = receipt["candidate_profiles"]["synthesizable_rtl"]["reduction"]
        self.assertIn("int64", runtime["variance"])
        self.assertIn("66_bit_square", rtl["variance"])
        self.assertIsNone(receipt["selected_profile"])

    def test_runtime_probe_is_deterministic_and_explicitly_not_board_evidence(self):
        receipt = self.module.derive_receipt(REFERENCE, QDQ)
        probe = receipt["runtime_probe"]
        self.assertEqual(probe["input_pattern"], "alternating_plus_minus_one_q16.16")
        self.assertEqual(probe["sha256"], self.module.canonical_sha256(probe["output"]))
        self.assertEqual(receipt["checkpoint_trace"]["authority"], "content_authenticated_fixed_runtime_not_board_authenticated")


if __name__ == "__main__":
    unittest.main()
