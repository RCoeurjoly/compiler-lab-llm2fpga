"""Adversarial tests for the TinyStories-1M Q/DQ semantics receipt."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/authenticate_tinystories_1m_qdq_semantics.py"
RECEIPT = ROOT / "artifacts/reference/tinystories-1m-qdq-semantics.json"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
REFERENCE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest")
PACKAGE = REFERENCE / "model_packages/tinystories-1m"


def load_semantics():
    spec = importlib.util.spec_from_file_location("tinystories_1m_qdq_semantics", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semantics = load_semantics()


class TinyStories1MQdqSemanticsTest(unittest.TestCase):
    def test_signed_quantization_is_half_away_and_saturating(self) -> None:
        # With Q8.24 scale 512, each Q16.16 input LSB is one half code.
        values = [-1000, -257, -255, -3, -1, 0, 1, 3, 255, 257, 1000]
        self.assertEqual(
            semantics.quantize_q16_to_int8(values, [512] * len(values)),
            [-128, -128, -128, -2, -1, 0, 1, 2, 127, 127, 127],
        )
        self.assertEqual(semantics.dequantize_int8_to_q16([-3, -1, 0, 1, 3], [384] * 5),
                         [-5, -2, 0, 2, 5])

    def test_quantization_rejects_invalid_scale_and_non_integer_domain(self) -> None:
        for scales in ([0], [-1]):
            with self.subTest(scales=scales), self.assertRaisesRegex(ValueError, "positive"):
                semantics.quantize_q16_to_int8([1], scales)
        for value in (math.nan, math.inf, -math.inf, 1.25):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "integer"):
                semantics.quantize_q16_to_int8([value], [512])

    def test_rtl_serial_weight_accumulation_uses_input_index_order_and_int64(self) -> None:
        value, terms = semantics.serial_weight_accumulate(
            activation_codes=[-128, 7, 127],
            activation_scales_q24=[3, 5, 11],
            weight_codes=[127, -3, -128],
        )
        self.assertEqual(terms, [-128 * 3 * 127, 7 * 5 * -3, 127 * 11 * -128])
        self.assertEqual(value, sum(terms))
        with self.assertRaisesRegex(ValueError, "same non-zero length"):
            semantics.serial_weight_accumulate([1], [1, 2], [1])

    def test_receipt_is_fail_closed_on_the_profile_authority_conflict(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema"], "tinystories-1m-qdq-semantics-v1")
        self.assertEqual(receipt["status"], "incomplete")
        self.assertEqual(receipt["selected_profile"], None)
        self.assertEqual(
            {reason["code"] for reason in receipt["incomplete_reasons"]},
            {
                "reference_profile_not_selected_by_frozen_contract",
                "accumulator_width_conflict",
                "activation_scale_granularity_conflict",
                "non_finite_policy_unauthenticated",
                "oracle_not_board_checkpoint_authenticated",
            },
        )
        witness = receipt["profile_conflict"]["rounding_witness"]
        self.assertEqual(witness["floating_integer_reference_code"], 0)
        self.assertEqual(witness["fixed_hardware_reference_code"], 1)

    def test_receipt_fully_describes_fixed_hardware_qdq(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        fixed = receipt["profiles"]["fixed_hardware_reference"]
        floating = receipt["profiles"]["floating_integer_reference"]
        self.assertEqual(floating["non_finite_policy"], "not_explicitly_rejected_by_reference_runtime")
        self.assertEqual(floating["accumulation"]["reduction_order"], "not_guaranteed_by_numpy_api")
        self.assertEqual(fixed["activation_conversion"]["rounding"], "nearest_ties_away_from_zero")
        self.assertEqual(fixed["activation_conversion"]["clamp"], [-128, 127])
        self.assertEqual(fixed["activation_conversion"]["zero_point"], 0)
        self.assertEqual(fixed["accumulation"]["reference_runtime"]["operation"], "numpy_matmul")
        self.assertEqual(fixed["accumulation"]["reference_runtime"]["reduction_order"],
                         "not_guaranteed_by_numpy_api")
        self.assertEqual(fixed["accumulation"]["synthesizable_rtl"]["logical_width_bits"], 64)
        self.assertEqual(fixed["accumulation"]["synthesizable_rtl"]["input_order"],
                         "ascending_input_index")
        self.assertEqual(fixed["weight_scale"]["axis"], "output_channel")
        self.assertEqual(fixed["activation_boundaries"]["count"], 97)
        self.assertEqual(fixed["activation_boundaries"]["placement"],
                         "module_input_and_module_output_except_lm_head_input_only")
        nonfinite = fixed["non_finite_behavior"]
        self.assertEqual(nonfinite["status"], "unauthenticated")
        self.assertFalse(nonfinite["explicit_reference_rejection"])
        self.assertEqual(
            nonfinite["pinned_environment_observation"]["parameter_q16_16_int32"],
            [-2147483648, 2147483647, -2147483648],
        )
        self.assertEqual(
            nonfinite["pinned_environment_observation"]["floating_reference_activation_codes"],
            [0, 127, -128],
        )
        self.assertEqual(nonfinite["pinned_environment_observation"]["scale_u24"],
                         "ValueError: Q8.24 scale does not fit unsigned 24-bit storage")

    def test_candidate_oracle_has_all_twelve_content_bound_checkpoints(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        oracle = receipt["candidate_oracle"]
        self.assertEqual(oracle["status"], "runtime_authenticated_not_board_checkpoint_authenticated")
        self.assertEqual(oracle["prompt_tokens"], [7454, 2402, 257, 640])
        self.assertEqual(oracle["next_token"], 11)
        self.assertEqual(oracle["checkpoint_order"], list(semantics.CHECKPOINT_SHAPES))
        self.assertEqual(set(oracle["checkpoints"]), set(semantics.CHECKPOINT_SHAPES))
        for name, shape in semantics.CHECKPOINT_SHAPES.items():
            checkpoint = oracle["checkpoints"][name]
            self.assertEqual(checkpoint["shape"], list(shape))
            self.assertEqual(checkpoint["dtype"], "signed_q16.16")
            self.assertEqual(
                checkpoint["sha256"],
                semantics.canonical_sha256({
                    "shape": list(shape),
                    "dtype": "signed_q16.16",
                    "values": checkpoint["values"],
                }),
            )
        self.assertEqual(oracle["sha256"], semantics.oracle_sha256(oracle))
        self.assertEqual(receipt["receipt_sha256"], semantics.receipt_sha256(receipt))

    @unittest.skipUnless(REFERENCE.is_dir() and PACKAGE.is_dir(), "authenticated reference unavailable")
    def test_receipt_authenticates_agpl_sources_and_transport_only_host(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["authority"]["license"]["spdx"], "AGPL-3.0-only")
        self.assertEqual(receipt["authority"]["git_revision"], "df1fc45b2ffcb26fddc19cfd57621e7eedf6153f")
        self.assertEqual(receipt["authority"]["host_role"], "transport_and_tokenizer_only")
        for source in receipt["authority"]["sources"]:
            path = REFERENCE / source["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source["sha256"])

    @unittest.skipUnless(REFERENCE.is_dir() and PACKAGE.is_dir(), "authenticated reference unavailable")
    def test_regeneration_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "receipt.json"
            completed = subprocess.run(
                [
                    "python", str(SCRIPT),
                    "--reference-root", str(REFERENCE),
                    "--contract", str(CONTRACT),
                    "--package", str(PACKAGE),
                    "--output", str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_bytes(), RECEIPT.read_bytes())

    def test_source_tamper_fails_before_oracle_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fake = Path(temporary) / "reference"
            fake.mkdir()
            (fake / "LICENSE").write_text("tampered", encoding="utf-8")
            # No dynamically supplied implementation runs before content
            # authentication rejects the first modified source.
            with self.assertRaisesRegex(semantics.SemanticsAuthenticationError, "source_hash_mismatch"):
                semantics.build_receipt(fake, CONTRACT, PACKAGE)


if __name__ == "__main__":
    unittest.main()
