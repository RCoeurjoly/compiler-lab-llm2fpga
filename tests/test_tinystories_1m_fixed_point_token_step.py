from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOWERER = ROOT / "scripts/pipeline/lower_fixed_point_token_step_to_calyx.py"
BLOCK_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json"
)
ATTENTION_FIXTURE = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json"
)
MLP_FIXTURE = (
    ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
)
SV_RECEIPT = (
    ROOT
    / "artifacts/reference/tinystories-1m-fixed-point-token-step-sv-receipt.json"
)


def load_lowerer():
    if not LOWERER.is_file():
        raise AssertionError("missing stateful token-step Calyx lowerer")
    spec = importlib.util.spec_from_file_location(
        "fixed_point_token_step_calyx", LOWERER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TokenStepTest(unittest.TestCase):
    def test_generated_main_exposes_stateful_transaction_contract(self):
        lowerer = load_lowerer()
        artifact = lowerer.generate_token_step_kernel(
            BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )

        self.assertEqual(artifact.futil.count("component main("), 1)
        self.assertIn(
            "component main(@go start: 1, valid: 1) -> (@done done: 1)",
            artifact.futil,
        )
        self.assertIn(
            "@external input_state_q16_16 = seq_mem_d1(64, 256, 8);",
            artifact.futil,
        )
        self.assertIn(
            "@external output_state_q16_16 = seq_mem_d1(64, 256, 8);",
            artifact.futil,
        )
        self.assertIn(
            "while token_valid_not.out with token_wait_for_valid_condition",
            artifact.futil,
        )
        self.assertIn(
            "block_input_q16_16.write_data = output_state_q16_16.read_data;",
            artifact.futil,
        )
        self.assertIn(
            "output_state_q16_16.write_data = block_output_q16_16.read_data;",
            artifact.futil,
        )
        self.assertEqual(len(artifact.provenance["expected_transactions"]), 2)
        self.assertEqual(
            artifact.provenance["expected_transactions"][1][
                "input_state_sha256"
            ],
            artifact.provenance["expected_transactions"][0][
                "output_state_sha256"
            ],
        )
        self.assertNotEqual(
            artifact.provenance["expected_transactions"][0][
                "output_state_sha256"
            ],
            artifact.provenance["expected_transactions"][1][
                "output_state_sha256"
            ],
        )
        self.assertFalse(
            set(artifact.provenance["host_preload_memories"])
            & set(artifact.provenance["hardware_owned_memories"])
        )

    def test_two_transactions_use_committed_hardware_state(self):
        lowerer = load_lowerer()
        artifact = lowerer.generate_token_step_kernel(
            BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )
        receipt = lowerer.run_token_step_sv(
            artifact, BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )

        self.assertEqual(artifact.futil.count("component main("), 1)
        self.assertIn("@go start: 1", artifact.futil)
        self.assertIn("valid: 1", artifact.futil)
        self.assertIn("@done done: 1", artifact.futil)
        self.assertEqual(len(receipt["transactions"]), 2)
        self.assertEqual(
            receipt["transactions"][1]["input_state_sha256"],
            receipt["transactions"][0]["output_state_sha256"],
        )
        self.assertTrue(receipt["reset"]["isolated"])
        self.assertEqual(
            receipt["synthesis"]["same_futil_sha256"],
            receipt["generated_artifacts"]["futil"]["sha256"],
        )
        self.assertEqual(receipt["execution"]["simulator_runs"], 1)
        self.assertEqual(receipt["execution"]["transaction_count"], 2)
        self.assertFalse(receipt["execution"]["host_intermediate"])
        self.assertFalse(receipt["execution"]["host_expected_output_preload"])
        self.assertTrue(all(cycles > 131072 for cycles in receipt["execution"]["cycles"]))

    def test_checked_in_receipt_is_self_hashed_and_rejects_tampering(self):
        lowerer = load_lowerer()
        self.assertTrue(SV_RECEIPT.is_file())
        receipt = json.loads(SV_RECEIPT.read_text(encoding="utf-8"))
        lowerer.validate_token_step_receipt(
            receipt,
            BLOCK_FIXTURE,
            ATTENTION_FIXTURE,
            MLP_FIXTURE,
            verify_artifacts=False,
        )
        unsigned = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        encoded = json.dumps(
            unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        self.assertEqual(receipt["receipt_sha256"], hashlib.sha256(encoded).hexdigest())

        tampered = copy.deepcopy(receipt)
        tampered["transactions"][1]["input_state_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "self-hash mismatch"):
            lowerer.validate_token_step_receipt(
                tampered,
                BLOCK_FIXTURE,
                ATTENTION_FIXTURE,
                MLP_FIXTURE,
                verify_artifacts=False,
            )

        resealed = copy.deepcopy(receipt)
        resealed["fixture_authorities"]["block"]["schema"] = "forged"
        unsigned = {
            key: value for key, value in resealed.items() if key != "receipt_sha256"
        }
        resealed["receipt_sha256"] = hashlib.sha256(
            json.dumps(
                unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "fixture authorities mismatch"):
            lowerer.validate_token_step_receipt(
                resealed,
                BLOCK_FIXTURE,
                ATTENTION_FIXTURE,
                MLP_FIXTURE,
                verify_artifacts=False,
            )

    def test_generated_harness_has_no_expected_or_feedback_preload(self):
        lowerer = load_lowerer()
        artifact = lowerer.generate_token_step_kernel(
            BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )
        block_lowerer = lowerer._block_lowerer()
        block, attention, mlp = block_lowerer._checked_fixtures(
            BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE
        )
        harness = lowerer._generated_harness(artifact, block, attention, mlp)

        self.assertNotIn("kExpected", harness)
        self.assertEqual(
            re.findall(
                r"output_state_q16_16__DOT__mem\[i\]\s*=\s*([^;]+);",
                harness,
            ),
            ["0"],
        )
        self.assertIn(
            "const auto second_input = read_state(root, true);", harness
        )
        self.assertNotIn("kSecond", harness)


if __name__ == "__main__":
    unittest.main()
