"""Regression tests for fixed-point implementation-profile selection."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/select_tinystories_1m_implementation_profile.py"
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
QDQ = ROOT / "artifacts/reference/tinystories-1m-qdq-semantics.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-implementation-profile.json"


def load_selector():
    spec = importlib.util.spec_from_file_location("tinystories_1m_implementation_profile", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


selector = load_selector()


class TinyStories1MImplementationProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.qdq = json.loads(QDQ.read_text(encoding="utf-8"))
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def _board_receipt(self) -> dict[str, object]:
        oracle = self.qdq["candidate_oracle"]
        authority = self.qdq["authority"]
        receipt: dict[str, object] = {
            "schema": selector.BOARD_SCHEMA,
            "profile": selector.PROFILE,
            "contract_sha256": selector.sha256_file(CONTRACT),
            "qdq_receipt_sha256": self.qdq["receipt_sha256"],
            "board": {"name": "YPCB-00338-1P1", "fpga_part": "xc7k480tffg1156-1"},
            "bitstream_sha256": "a" * 64,
            "source_hashes": {item["path"]: item["sha256"] for item in authority["sources"]},
            "prompt_tokens": self.contract["reference"]["prompt_tokens"],
            "output_tokens": self.contract["reference"]["tokens"],
            "trace": {
                "block_index": oracle["block_index"],
                "checkpoint_order": oracle["checkpoint_order"],
                "checkpoints": oracle["checkpoints"],
                "sha256": oracle["sha256"],
            },
        }
        receipt["receipt_sha256"] = selector.canonical_sha256(receipt)
        return receipt

    def _write_board(self, root: Path, value: dict[str, object]) -> Path:
        path = root / "board.json"
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        return path

    def test_checked_in_profile_is_explicitly_unresolved_without_board_trace(self) -> None:
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["schema"], selector.SCHEMA)
        self.assertEqual(profile["version"], 1)
        self.assertEqual(profile["status"], "unresolved")
        self.assertIsNone(profile["selected_profile"])
        self.assertEqual(profile["board_evidence"], None)
        self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_checkpoint_receipt_missing")
        self.assertEqual(profile["profile_sha256"], selector.profile_sha256(profile))

    def test_selection_requires_complete_board_checkpoint_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            board = self._write_board(Path(temporary), self._board_receipt())
            profile = selector.build_profile(CONTRACT, QDQ, board)
        self.assertEqual(profile["status"], "selected")
        self.assertEqual(profile["selected_profile"], selector.PROFILE)
        self.assertEqual(profile["board_evidence"]["trace_sha256"], self.qdq["candidate_oracle"]["sha256"])

    def test_conflicting_profile_and_trace_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            board = self._board_receipt()
            board["profile"] = "floating_integer_reference"
            board["receipt_sha256"] = selector.canonical_sha256({k: v for k, v in board.items() if k != "receipt_sha256"})
            profile = selector.build_profile(CONTRACT, QDQ, self._write_board(Path(temporary), board))
            self.assertEqual(profile["status"], "unresolved")
            self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_profile_mismatch")
            board = self._board_receipt()
            board["trace"] = copy.deepcopy(board["trace"])
            board["trace"]["checkpoints"]["block.output"]["values"][0] += 1
            board["receipt_sha256"] = selector.canonical_sha256({k: v for k, v in board.items() if k != "receipt_sha256"})
            profile = selector.build_profile(CONTRACT, QDQ, self._write_board(Path(temporary), board))
            self.assertEqual(profile["status"], "unresolved")
            self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_trace_mismatch")

    def test_qdq_or_contract_tampering_is_rejected_not_reinterpreted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qdq = copy.deepcopy(self.qdq)
            qdq["receipt_sha256"] = "0" * 64
            qdq_path = root / "qdq.json"
            qdq_path.write_text(json.dumps(qdq), encoding="utf-8")
            with self.assertRaisesRegex(selector.ProfileSelectionError, "qdq_receipt_hash_mismatch"):
                selector.build_profile(CONTRACT, qdq_path)


if __name__ == "__main__":
    unittest.main()
