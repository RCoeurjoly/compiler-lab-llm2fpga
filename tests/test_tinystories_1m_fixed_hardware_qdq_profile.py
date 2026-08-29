"""Tests for the runtime-authenticated fixed-hardware Q/DQ compiler profile."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/fixed_hardware_qdq_profile.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
QDQ = ROOT / "artifacts/reference/tinystories-1m-qdq-semantics.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"


def load_profile_module():
    spec = importlib.util.spec_from_file_location("tinystories_1m_fixed_hardware_qdq_profile", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedHardwareQdqProfileTest(unittest.TestCase):
    def test_profile_is_runtime_authenticated_with_all_evidenced_semantics_and_trace(self) -> None:
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["schema"], "tinystories-1m-fixed-hardware-qdq-profile-v1")
        self.assertEqual(profile["version"], 1)
        self.assertEqual(profile["status"], "runtime_authenticated_not_board_checkpoint_authenticated")
        self.assertEqual(profile["profile"], "fixed_hardware_reference")
        self.assertFalse(profile["board_authenticated"])
        semantics = profile["semantics"]
        self.assertEqual(semantics["activation_conversion"]["scale"], "per-channel_unsigned_q8.24_u24")
        self.assertEqual(semantics["activation_conversion"]["rounding"], "nearest_ties_away_from_zero")
        self.assertEqual(semantics["activation_conversion"]["clamp"], [-128, 127])
        self.assertEqual(semantics["accumulation"]["synthesizable_rtl"], {
            "operation": "serial_multiply_accumulate", "input_order": "ascending_input_index",
            "logical_width_bits": 64, "overflow": "twos_complement_wrap",
        })
        self.assertEqual(semantics["weight_scale"]["axis"], "output_channel")
        self.assertEqual(semantics["weight_scale"]["bias_order"], "add_signed_q16.16_bias_after_weight_scale")
        trace = profile["software_trace"]
        self.assertEqual(trace["next_token"], 11)
        self.assertEqual(len(trace["checkpoint_order"]), 12)
        self.assertEqual(set(trace["checkpoint_order"]), set(trace["checkpoints"]))

    def test_profile_validation_rejects_rehashed_qdq_semantics_changes(self) -> None:
        module = load_profile_module()
        receipt = json.loads(QDQ.read_text(encoding="utf-8"))
        receipt = copy.deepcopy(receipt)
        receipt["profiles"]["fixed_hardware_reference"]["accumulation"]["synthesizable_rtl"]["logical_width_bits"] = 32
        receipt["receipt_sha256"] = module.canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "qdq.json"
            changed.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(module.FixedHardwareProfileError, "qdq_artifact_identity_mismatch"):
                module.build_profile(CONTRACT, changed)

    def test_profile_self_hash_and_checkpoint_hashes_are_verified(self) -> None:
        module = load_profile_module()
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["profile_sha256"], module.profile_sha256(profile))
        module.validate_profile(PROFILE, CONTRACT, QDQ)


if __name__ == "__main__":
    unittest.main()
