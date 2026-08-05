"""Behavioral tests for durable RC observable-oracle shard artifacts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from TinyStories.rc_working_contract import (
    RC_WORKING_PIPELINE_ALIAS,
    RC_WORKING_SOURCE_MODEL_KEY,
    load_corpus,
    tokenize,
)

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

    def test_record_rejects_nonlowest_argmax_for_a_tie(self) -> None:
        """Catches changing the RC tie rule from lowest index to another lane."""

        with self.assertRaisesRegex(ValueError, "argmax"):
            pack_record([7, 7, 0, 0, 0, 0], 1)
        with self.assertRaisesRegex(ValueError, "argmax"):
            unpack_record("0001000000000707")


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
        self.export_hash = "a" * 64
        self.manifest_hash = "b" * 64
        self.receipt = {
            "artifacts": {
                "exported_program_sha256": self.export_hash,
                "export_manifest_sha256": self.manifest_hash,
                "reference_sha256": "c" * 64,
                "image_sha256": "d" * 64,
                "image_manifest_sha256": "e" * 64,
                "generator_sha256": "f" * 64,
                "contract_sha256": "0" * 64,
            },
            "python_version": "3.12.0",
            "pytorch_version": "test",
            "pytorch_num_threads": 1,
        }
        self.reference = self._reference()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _reference(
        self,
        *,
        export_hash: str | None = None,
        manifest_hash: str | None = None,
    ) -> dict[str, object]:
        corpus = load_corpus(ROOT / "TinyStories" / "rc_working_corpus.json")
        codes = [1, 2, 3, 4, 5, 0]
        token_id = 4
        rows = []
        corpus_rows = []
        for case in corpus:
            tokens = tokenize(case["text"])
            rows.append(
                {
                    "schema_version": 1,
                    "source_model_key": RC_WORKING_SOURCE_MODEL_KEY,
                    "pipeline_alias": RC_WORKING_PIPELINE_ALIAS,
                    "case_id": case["id"],
                    "token_ids": tokens,
                    "output_qparams": {"scale": 1.0, "zero_point": 0},
                    "output_codes_i8": codes,
                    "logits": [float(code) for code in codes],
                    "token_id": token_id,
                }
            )
            corpus_rows.append({"id": case["id"], "text": case["text"], "token_ids": tokens})
        return {
            "schema_version": 1,
            "source_model_key": RC_WORKING_SOURCE_MODEL_KEY,
            "pipeline_alias": RC_WORKING_PIPELINE_ALIAS,
            "exported_program_sha256": export_hash or self.export_hash,
            "export_manifest_sha256": manifest_hash or self.manifest_hash,
            "export_manifest": {},
            "calibration_input_ids": [corpus_rows[0]["token_ids"]],
            "corpus": corpus_rows,
            "output_qparams": {"scale": 1.0, "zero_point": 0},
            "results": rows,
        }

    def _verified_metadata(self, *, start: int, stop: int) -> dict[str, object]:
        """Represent a receipt after the public file verifier has checked it."""

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
                "sha256": "1" * 64,
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
            exported_program_sha256=self.export_hash,
            export_manifest_sha256=self.manifest_hash,
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

        reference = self._reference()
        reference["results"][0] = {**reference["results"][0], "token_id": 5}
        with self.assertRaisesRegex(ValueError, "reference"):
            oracle.generate_shard(
                evaluator=DeterministicEvaluator(),
                start=4,
                stop=6,
                output_dir=self.path,
                receipt=self.receipt,
                reference=reference,
                exported_program_sha256=self.export_hash,
                export_manifest_sha256=self.manifest_hash,
            )
        self.assertFalse((self.path / "shard-4-6.hex").exists())

    def test_generate_rejects_empty_incomplete_or_wrongly_bound_reference(self) -> None:
        """Catches a payload writer accepting a partial or different PT2E authority."""

        invalid_references = [
            {**self._reference(), "results": []},
            {**self._reference(), "results": self._reference()["results"][:-1]},
            self._reference(export_hash="1" * 64),
            self._reference(manifest_hash="2" * 64),
        ]
        for reference in invalid_references:
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(ValueError, "reference"):
                    oracle.generate_shard(
                        evaluator=DeterministicEvaluator(),
                        start=4,
                        stop=6,
                        output_dir=self.path,
                        receipt=self.receipt,
                        reference=reference,
                        exported_program_sha256=self.export_hash,
                        export_manifest_sha256=self.manifest_hash,
                    )
        self.assertFalse((self.path / "shard-4-6.hex").exists())

    def test_file_merge_rejects_corrupted_payload_and_malformed_receipt(self) -> None:
        """Catches claiming coverage from payload bytes or provenance not verified from disk."""

        oracle.generate_shard(
            evaluator=DeterministicEvaluator(),
            start=4,
            stop=6,
            output_dir=self.path,
            receipt=self.receipt,
            reference=self.reference,
            exported_program_sha256=self.export_hash,
            export_manifest_sha256=self.manifest_hash,
        )
        metadata_path = self.path / "shard-4-6.json"
        payload_path = self.path / "shard-4-6.hex"
        payload_path.write_bytes(b"0004010504030201\n0004000504030201\n")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            oracle.merge_oracle_files([metadata_path], self.path / "coverage.json")

        generated = json.loads(metadata_path.read_text(encoding="utf-8"))
        for invalid_receipt in (None, {"artifacts": {}}):
            generated["receipt"] = invalid_receipt
            metadata_path.write_text(json.dumps(generated), encoding="utf-8")
            with self.subTest(receipt=invalid_receipt):
                with self.assertRaisesRegex(ValueError, "receipt"):
                    oracle.verify_shard(metadata_path)
                with self.assertRaisesRegex(ValueError, "receipt"):
                    oracle.merge_oracle_files([metadata_path], self.path / "coverage.json")

    def test_file_verify_and_merge_reject_invalid_elapsed_seconds(self) -> None:
        """Catches a complete-coverage claim with absent or unusable timing provenance."""

        oracle.generate_shard(
            evaluator=DeterministicEvaluator(),
            start=4,
            stop=6,
            output_dir=self.path,
            receipt=self.receipt,
            reference=self.reference,
            exported_program_sha256=self.export_hash,
            export_manifest_sha256=self.manifest_hash,
        )
        metadata_path = self.path / "shard-4-6.json"
        generated = json.loads(metadata_path.read_text(encoding="utf-8"))
        for invalid_elapsed in (None, "0.1", True, float("inf"), -0.1):
            invalid = dict(generated)
            if invalid_elapsed is None:
                invalid.pop("elapsed_seconds")
            else:
                invalid["elapsed_seconds"] = invalid_elapsed
            metadata_path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.subTest(elapsed_seconds=invalid_elapsed):
                with self.assertRaisesRegex(ValueError, "elapsed"):
                    oracle.verify_shard(metadata_path)
                with self.assertRaisesRegex(ValueError, "elapsed"):
                    oracle.merge_oracle_files([metadata_path], self.path / "coverage.json")

    def test_verified_receipt_merge_rejects_gap_and_overlap(self) -> None:
        """Catches a coverage proof that accepts non-partitioning verified ranges."""

        first = self._verified_metadata(start=0, stop=1)
        last = self._verified_metadata(start=1, stop=oracle.TOTAL_CONTEXTS)
        merged = oracle._merge_verified_oracle_receipts([last, first])
        self.assertTrue(merged["coverage"]["complete"])

        gapped = self._verified_metadata(start=2, stop=oracle.TOTAL_CONTEXTS)
        with self.assertRaisesRegex(ValueError, "gap"):
            oracle._merge_verified_oracle_receipts([first, gapped])

        overlapping = self._verified_metadata(start=0, stop=oracle.TOTAL_CONTEXTS)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            oracle._merge_verified_oracle_receipts([first, overlapping])
