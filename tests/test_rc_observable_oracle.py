"""Behavioral tests for durable RC observable-oracle shard artifacts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "build_rc_observable_oracle.py"
SPEC = importlib.util.spec_from_file_location("build_rc_observable_oracle", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)

context_from_index = oracle.context_from_index
index_from_context = oracle.index_from_context
pack_record = oracle.pack_record
unpack_record = oracle.unpack_record


class ObservableOracleFormatTests(unittest.TestCase):
    def test_context_index_round_trip_uses_rightmost_token_as_fastest(self) -> None:
        """Catches a reversed base-six enumeration order."""

        self.assertEqual(context_from_index(0), [0, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(context_from_index(1), [0, 0, 0, 0, 0, 0, 0, 1])
        self.assertEqual(context_from_index(6), [0, 0, 0, 0, 0, 0, 1, 0])
        self.assertEqual(index_from_context([5] * 8), 1_679_615)

    def test_record_round_trip_preserves_signed_codes_and_argmax(self) -> None:
        """Catches lost int8 sign bits or a changed record lane order."""

        word = pack_record([-128, -1, 0, 127, 7, 7], 3)
        self.assertEqual(word, "000307077f00ff80")
        self.assertEqual(unpack_record(word), ([-128, -1, 0, 127, 7, 7], 3))

    def test_unpack_record_rejects_reserved_bits_and_invalid_token(self) -> None:
        """Catches accepting words the SV fixture must reject."""

        with self.assertRaisesRegex(ValueError, "reserved"):
            unpack_record("0100000000000000")
        with self.assertRaisesRegex(ValueError, "token"):
            unpack_record("0006000000000000")

    def test_record_rejects_token_that_is_not_lowest_index_argmax(self) -> None:
        """Catches accepting a token that disagrees with the raw observables."""

        with self.assertRaisesRegex(ValueError, "argmax"):
            pack_record([1, 2, 3, 4, 5, 0], 0)
        with self.assertRaisesRegex(ValueError, "argmax"):
            unpack_record("0000000504030201")


class DeterministicEvaluator:
    """A batch-one evaluator double that supplies a prevalidated test record."""

    def __call__(self, tokens: list[int]) -> tuple[list[int], int]:
        if len(tokens) != 8:
            raise ValueError("test evaluator needs a batch-one context")
        return [1, 2, 3, 4, 5, 0], 4


class ObservableOracleShardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name)
        self.receipt = {"producer": "test-observable-oracle"}
        self.reference = {
            "results": [
                {
                    "token_ids": context_from_index(4),
                    "output_codes_i8": [1, 2, 3, 4, 5, 0],
                    "token_id": 4,
                }
            ]
        }

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _receipt(self, *, start: int, stop: int) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": "complete",
            "receipt": self.receipt,
            "record_format": oracle.RECORD_FORMAT,
            "enumeration": {
                "kind": "base-six-lexical-rightmost-fastest",
                "start": start,
                "stop": stop,
                "total_contexts": oracle.TOTAL_CONTEXTS,
            },
            "payload": {
                "file": f"shard-{start}-{stop}.hex",
                "sha256": "a" * 64,
                "records": stop - start,
                "bytes": 17 * (stop - start),
            },
        }

    def test_generate_shard_streams_payload_and_records_digest(self) -> None:
        """Catches buffering, malformed-line, or digest-accounting regressions."""

        receipt = oracle.generate_shard(
            evaluator=DeterministicEvaluator(),
            start=4,
            stop=6,
            output_dir=self.path,
            receipt=self.receipt,
            reference=self.reference,
        )

        payload_path = self.path / "shard-4-6.hex"
        payload = payload_path.read_bytes()
        self.assertEqual(receipt["enumeration"]["start"], 4)
        self.assertEqual(receipt["payload"]["records"], 2)
        self.assertEqual(
            payload_path.read_text(encoding="ascii").splitlines(),
            ["0004000504030201", "0004000504030201"],
        )
        self.assertEqual(len(payload), 2 * 17)
        self.assertEqual(receipt["payload"]["bytes"], len(payload))
        self.assertEqual(receipt["payload"]["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(
            json.loads((self.path / "shard-4-6.json").read_text(encoding="utf-8")),
            receipt,
        )

    def test_generate_shard_rejects_reference_discrepancy_before_writing(self) -> None:
        """Catches generation from an evaluator that drifted from frozen PT2E."""

        reference = {"results": [{**self.reference["results"][0], "token_id": 5}]}
        with self.assertRaisesRegex(ValueError, "reference"):
            oracle.generate_shard(
                evaluator=DeterministicEvaluator(),
                start=4,
                stop=6,
                output_dir=self.path,
                receipt=self.receipt,
                reference=reference,
            )
        self.assertFalse((self.path / "shard-4-6.hex").exists())

    def test_merge_oracle_receipts_requires_contiguous_complete_coverage(self) -> None:
        """Catches an oracle merge that calls a gapped shard set complete."""

        first = self._receipt(start=0, stop=1)
        last = self._receipt(start=1, stop=oracle.TOTAL_CONTEXTS)
        merged = oracle.merge_oracle_receipts([last, first])
        self.assertTrue(merged["coverage"]["complete"])
        self.assertEqual(merged["coverage"]["start"], 0)
        self.assertEqual(merged["coverage"]["stop"], oracle.TOTAL_CONTEXTS)
        gapped_last = {
            **last,
            "enumeration": {**last["enumeration"], "start": 2},
            "payload": {
                **last["payload"],
                "records": oracle.TOTAL_CONTEXTS - 2,
                "bytes": 17 * (oracle.TOTAL_CONTEXTS - 2),
            },
        }
        with self.assertRaisesRegex(ValueError, "gap"):
            oracle.merge_oracle_receipts([first, gapped_last])
