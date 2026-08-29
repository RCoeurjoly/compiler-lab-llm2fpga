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
        codes = {item["code"] for item in receipt["conflicts"]}
        self.assertIn("layernorm_overflow_domain_conflict", codes)
        self.assertIn("layernorm_affine_output_width_conflict", codes)

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

    def test_executable_reduction_overflow_witness_runs_runtime_and_independent_rtl_model(self):
        witness = self.module.overflow_witness(REFERENCE)
        self.assertEqual(witness["input_q16_16"], [-2**31, 2**31 - 1] * 32)
        self.assertEqual(witness["runtime"], {"status": "raised", "exception": "ValueError: isqrt() argument must be nonnegative"})
        rtl = witness["independent_rtl_width_model"]
        self.assertEqual(rtl["variance_64"], 4611686016279947206)
        self.assertEqual(rtl["normalized_first_two"], [-65536, 65536])

    def test_affine_output_width_witness_cannot_be_promoted_to_equivalence(self):
        witness = self.module.affine_overflow_witness()
        self.assertEqual(witness["normalized_q16_16"], [-370727, 370727])
        self.assertEqual(witness["gamma_q16_16"], 2**31 - 1)
        self.assertEqual(witness["runtime_int64_affine_output"], [-12147982331, 12147982330])
        self.assertEqual(witness["rtl_signed_int32_out_y"], [736919557, -736919558])


if __name__ == "__main__":
    unittest.main()
