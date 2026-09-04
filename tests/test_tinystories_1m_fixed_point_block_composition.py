from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
BLOCK_CAPTURE = ROOT / "TinyStories/capture_fixed_point_block_composition_slice.py"


def load_capture():
    if not BLOCK_CAPTURE.is_file():
        raise AssertionError("missing authenticated block-composition capture module")
    spec = importlib.util.spec_from_file_location(
        "fixed_point_block_composition_capture", BLOCK_CAPTURE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def flatten(values):
    for value in values:
        if isinstance(value, list):
            yield from flatten(value)
        else:
            yield value


def signed_i64_add(left: int, right: int) -> int:
    unsigned = (left + right) & ((1 << 64) - 1)
    return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned


def reseal_block_fixture(fixture: dict) -> None:
    record = fixture["tensors"]["block_output_q16_16"]
    payload = {
        key: record[key] for key in ("semantic", "shape", "dtype", "values")
    }
    record["canonical_sha256"] = canonical_sha256(payload)
    raw = b"".join(struct.pack("<q", value) for value in flatten(record["values"]))
    record["little_endian_int64_sha256"] = hashlib.sha256(raw).hexdigest()
    record["bytes"] = len(raw)
    tensor_receipts = {
        "block_output_q16_16": {
            key: record[key]
            for key in (
                "semantic",
                "shape",
                "dtype",
                "canonical_sha256",
                "little_endian_int64_sha256",
                "bytes",
            )
        }
    }
    binding_payload = {
        key: fixture[key]
        for key in (
            "schema",
            "status",
            "identity",
            "prompt_tokens",
            "slice",
            "arithmetic",
            "linked_attention",
            "linked_mlp",
        )
    } | {"tensor_receipts": tensor_receipts}
    binding = canonical_sha256(binding_payload)
    fixture["tensor_fixture_receipt_sha256"] = binding
    record["fixture_receipt_sha256"] = binding
    unsigned = {
        key: value for key, value in fixture.items() if key != "receipt_sha256"
    }
    fixture["receipt_sha256"] = canonical_sha256(unsigned)


class BlockCompositionTest(unittest.TestCase):
    def test_block_fixture_links_both_slices_and_replays_final_residual(self):
        """Catches a missing authority link or incorrect final residual."""
        capture_block = load_capture()
        fixture = capture_block.verify_fixture(BLOCK_FIXTURE)
        capture_block.verify_block_output_replay(BLOCK_FIXTURE)
        attention = json.loads(ATTENTION_FIXTURE.read_text(encoding="utf-8"))
        mlp = json.loads(MLP_FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual(fixture["slice"], {"block": 0, "rows": 4, "width": 64})
        self.assertEqual(
            fixture["tensors"]["block_output_q16_16"]["shape"], [4, 64]
        )
        self.assertEqual(
            fixture["linked_attention"]["receipt_sha256"],
            attention["receipt_sha256"],
        )
        self.assertEqual(
            fixture["linked_mlp"]["receipt_sha256"], mlp["receipt_sha256"]
        )
        attention_residual = attention["tensors"]["attention_residual_q16_16"][
            "values"
        ]
        c_proj_output = mlp["tensors"]["c_proj_output_q16_16"]["values"]
        independently_added = [
            [signed_i64_add(left, right) for left, right in zip(left_row, right_row)]
            for left_row, right_row in zip(attention_residual, c_proj_output)
        ]
        self.assertEqual(
            fixture["tensors"]["block_output_q16_16"]["values"],
            independently_added,
        )

    def test_fixture_contains_only_new_output_and_hash_only_link_records(self):
        """Catches duplication of attention/MLP tensor values in the new fixture."""
        fixture = load_capture().verify_fixture(BLOCK_FIXTURE)
        output = fixture["tensors"]["block_output_q16_16"]

        self.assertEqual(set(fixture["tensors"]), {"block_output_q16_16"})
        self.assertEqual(output["semantic"], "block_0_output_q16_16")
        self.assertEqual(output["dtype"], "int64")
        self.assertEqual(output["bytes"], 2048)
        self.assertEqual(
            output["canonical_sha256"],
            "762fe81857a2460b50c9375a56ef8378b7938d8f7fcfc7ec16bd73fefa063ef4",
        )
        self.assertEqual(
            output["little_endian_int64_sha256"],
            "61a7016bc7936ae32cefdf8153cf4560454c662e6c0ea6351144f3a5b377bedf",
        )
        self.assertEqual(len(fixture["linked_attention"]["tensor_receipts"]), 61)
        self.assertEqual(len(fixture["linked_mlp"]["tensor_receipts"]), 25)
        self.assertNotIn('"values"', json.dumps(fixture["linked_attention"]))
        self.assertNotIn('"values"', json.dumps(fixture["linked_mlp"]))
        unsigned = {
            key: value for key, value in fixture.items() if key != "receipt_sha256"
        }
        self.assertEqual(fixture["receipt_sha256"], canonical_sha256(unsigned))

    def test_replay_rejects_fully_resealed_block_output_mutation(self):
        """Catches a replay that trusts a self-consistent but wrong final output."""
        capture_block = load_capture()
        mutated = json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        mutated["tensors"]["block_output_q16_16"]["values"][0][0] += 1
        reseal_block_fixture(mutated)

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "resealed-output.json"
            candidate.write_text(json.dumps(mutated), encoding="utf-8")
            capture_block.verify_fixture(candidate)
            with self.assertRaisesRegex(ValueError, "block output residual replay"):
                capture_block.verify_block_output_replay(candidate)

    def test_fixture_rejects_resealed_linked_record_mutation(self):
        """Catches accepting a linked record hash that differs from its authority."""
        capture_block = load_capture()
        mutated = copy.deepcopy(
            json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        )
        mutated["linked_mlp"]["tensor_receipts"]["c_proj_output_q16_16"][
            "canonical_sha256"
        ] = "0" * 64
        reseal_block_fixture(mutated)

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "resealed-linked-record.json"
            candidate.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "linked mlp mismatch"):
                capture_block.verify_fixture(candidate)

    def test_fixture_rejects_resealed_linked_identity_mutation(self):
        """Catches accepting a linked fixture with a different source identity."""
        capture_block = load_capture()
        mutated = copy.deepcopy(
            json.loads(BLOCK_FIXTURE.read_text(encoding="utf-8"))
        )
        mutated["linked_attention"]["identity"]["adapter_sha256"] = "0" * 64
        reseal_block_fixture(mutated)

        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "resealed-linked-identity.json"
            candidate.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "linked attention mismatch"):
                capture_block.verify_fixture(candidate)


if __name__ == "__main__":
    unittest.main()
