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

    def _board_capture(self, bitstream_sha256: str) -> dict[str, object]:
        oracle = self.qdq["candidate_oracle"]
        trace = {
            "block_index": oracle["block_index"],
            "checkpoint_order": oracle["checkpoint_order"],
            "checkpoints": oracle["checkpoints"],
        }
        trace["sha256"] = selector.canonical_sha256(trace)
        return {
            "schema": selector.CAPTURE_SCHEMA,
            "capture_method": "board_debug_csr_readback",
            "board": {"name": "YPCB-00338-1P1", "fpga_part": "xc7k480tffg1156-1"},
            "bitstream_sha256": bitstream_sha256,
            "prompt_tokens": self.contract["reference"]["prompt_tokens"],
            "output_tokens": self.contract["reference"]["tokens"],
            "trace": trace,
        }

    def _board_receipt(self, root: Path) -> tuple[Path, dict[str, object]]:
        authority = self.qdq["authority"]
        bitstream = root / "tinystories.bit"
        bitstream.write_bytes(b"test bitstream evidence")
        bitstream_sha256 = selector.sha256_file(bitstream)
        manifest = root / "bitstream-manifest.json"
        manifest.write_text(json.dumps({
            "schema": selector.BITSTREAM_MANIFEST_SCHEMA,
            "bitstream_path": str(bitstream), "bitstream_sha256": bitstream_sha256,
            "build_provenance": {"build_id": "test-only"},
        }, sort_keys=True), encoding="utf-8")
        transcript = root / "board-transcript.txt"
        transcript.write_text("raw board debug-CSR readback transcript\n", encoding="utf-8")
        tool = root / "capture-tool.py"
        tool.write_text("# test-only capture tool identity\n", encoding="utf-8")
        protocol = root / "capture-protocol.md"
        protocol.write_text("# test-only capture protocol identity\n", encoding="utf-8")
        capture = root / "board-capture.json"
        capture.write_text(json.dumps(self._board_capture(bitstream_sha256), sort_keys=True), encoding="utf-8")
        receipt: dict[str, object] = {
            "schema": selector.BOARD_SCHEMA,
            "profile": selector.PROFILE,
            "contract_sha256": selector.sha256_file(CONTRACT),
            "qdq_receipt_sha256": self.qdq["receipt_sha256"],
            "board": {"name": "YPCB-00338-1P1", "fpga_part": "xc7k480tffg1156-1"},
            "bitstream": {"path": str(bitstream), "sha256": bitstream_sha256,
                          "manifest_path": str(manifest), "manifest_sha256": selector.sha256_file(manifest)},
            "source_hashes": {item["path"]: item["sha256"] for item in authority["sources"]},
            "capture": {"path": str(capture), "sha256": selector.sha256_file(capture),
                        "transcript_path": str(transcript), "transcript_sha256": selector.sha256_file(transcript),
                        "tool_path": str(tool), "tool_sha256": selector.sha256_file(tool),
                        "protocol_path": str(protocol), "protocol_sha256": selector.sha256_file(protocol)},
        }
        receipt["receipt_sha256"] = selector.canonical_sha256(receipt)
        return self._write_board(root, receipt), receipt

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

    def test_self_hashed_fabricated_board_evidence_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            board, _ = self._board_receipt(Path(temporary))
            profile = selector.build_profile(CONTRACT, QDQ, board)
        self.assertEqual(profile["status"], "unresolved")
        self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_receipt_not_approved")

    def test_explicitly_approved_file_backed_fixture_exercises_selected_path(self) -> None:
        """A test-only registry entry models the separate evidence-review act."""
        with tempfile.TemporaryDirectory() as temporary:
            board_path, board = self._board_receipt(Path(temporary))
            board_file_sha256 = selector.sha256_file(board_path)
            original = selector.APPROVED_BOARD_RECEIPTS
            selector.APPROVED_BOARD_RECEIPTS = {board_file_sha256: {
                "bitstream_sha256": board["bitstream"]["sha256"],
                "capture_sha256": board["capture"]["sha256"],
            }}
            try:
                profile = selector.build_profile(CONTRACT, QDQ, board_path)
            finally:
                selector.APPROVED_BOARD_RECEIPTS = original
        self.assertEqual(profile["status"], "selected")
        self.assertEqual(profile["selected_profile"], selector.PROFILE)
        self.assertEqual(profile["board_evidence"]["path"], str(board_path))
        self.assertEqual(profile["board_evidence"]["sha256"], board_file_sha256)

    def test_malformed_board_json_and_nan_are_unresolved_not_exceptions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            malformed = root / "malformed-board.json"
            malformed.write_text("{not JSON", encoding="utf-8")
            profile = selector.build_profile(CONTRACT, QDQ, malformed)
            self.assertEqual(profile["status"], "unresolved")
            self.assertEqual(profile["unresolved_reasons"][0]["code"], "invalid_json")
            board_path, board = self._board_receipt(root)
            board["board"]["temperature_c"] = float("nan")
            board["receipt_sha256"] = "ignored because NaN is not canonical"
            board_path = self._write_board(root, board)
            profile = selector.build_profile(CONTRACT, QDQ, board_path)
        self.assertEqual(profile["status"], "unresolved")
        self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_evidence_invalid")

    def test_conflicting_profile_and_trace_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            board_path, board = self._board_receipt(root)
            board["profile"] = "floating_integer_reference"
            board["receipt_sha256"] = selector.canonical_sha256({k: v for k, v in board.items() if k != "receipt_sha256"})
            board_path = self._write_board(root, board)
            original = selector.APPROVED_BOARD_RECEIPTS
            selector.APPROVED_BOARD_RECEIPTS = {selector.sha256_file(board_path): {
                "bitstream_sha256": board["bitstream"]["sha256"], "capture_sha256": board["capture"]["sha256"]}}
            profile = selector.build_profile(CONTRACT, QDQ, board_path)
            self.assertEqual(profile["status"], "unresolved")
            self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_profile_mismatch")
            selector.APPROVED_BOARD_RECEIPTS = original
            board_path, board = self._board_receipt(root)
            capture_path = Path(board["capture"]["path"])
            capture = json.loads(capture_path.read_text(encoding="utf-8"))
            capture["trace"] = copy.deepcopy(capture["trace"])
            capture["trace"]["checkpoints"]["block.output"]["values"][0] += 1
            changed = capture["trace"]["checkpoints"]["block.output"]
            changed["sha256"] = selector.canonical_sha256({
                "shape": changed["shape"], "dtype": changed["dtype"], "values": changed["values"]})
            capture["trace"]["sha256"] = selector.canonical_sha256({
                "block_index": capture["trace"]["block_index"], "checkpoint_order": capture["trace"]["checkpoint_order"],
                "checkpoints": capture["trace"]["checkpoints"]})
            capture_path.write_text(json.dumps(capture, sort_keys=True), encoding="utf-8")
            board["capture"]["sha256"] = selector.sha256_file(capture_path)
            board["receipt_sha256"] = selector.canonical_sha256({k: v for k, v in board.items() if k != "receipt_sha256"})
            board_path = self._write_board(root, board)
            selector.APPROVED_BOARD_RECEIPTS = {selector.sha256_file(board_path): {
                "bitstream_sha256": board["bitstream"]["sha256"], "capture_sha256": board["capture"]["sha256"]}}
            profile = selector.build_profile(CONTRACT, QDQ, board_path)
            self.assertEqual(profile["status"], "unresolved")
            self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_trace_mismatch")
            selector.APPROVED_BOARD_RECEIPTS = original

    def test_boolean_checkpoint_substitution_is_rejected_even_when_rehashed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            board_path, board = self._board_receipt(root)
            capture_path = Path(board["capture"]["path"])
            capture = json.loads(capture_path.read_text(encoding="utf-8"))
            capture["trace"]["checkpoints"]["block.output"]["values"][0] = True
            changed = capture["trace"]["checkpoints"]["block.output"]
            changed["sha256"] = selector.canonical_sha256({
                "shape": changed["shape"], "dtype": changed["dtype"], "values": changed["values"]})
            capture["trace"]["sha256"] = selector.canonical_sha256({
                "block_index": capture["trace"]["block_index"], "checkpoint_order": capture["trace"]["checkpoint_order"],
                "checkpoints": capture["trace"]["checkpoints"]})
            capture_path.write_text(json.dumps(capture, sort_keys=True), encoding="utf-8")
            board["capture"]["sha256"] = selector.sha256_file(capture_path)
            board["receipt_sha256"] = selector.canonical_sha256({k: v for k, v in board.items() if k != "receipt_sha256"})
            board_path = self._write_board(root, board)
            original = selector.APPROVED_BOARD_RECEIPTS
            selector.APPROVED_BOARD_RECEIPTS = {selector.sha256_file(board_path): {
                "bitstream_sha256": board["bitstream"]["sha256"], "capture_sha256": board["capture"]["sha256"]}}
            try:
                profile = selector.build_profile(CONTRACT, QDQ, board_path)
            finally:
                selector.APPROVED_BOARD_RECEIPTS = original
        self.assertEqual(profile["status"], "unresolved")
        self.assertEqual(profile["unresolved_reasons"][0]["code"], "board_checkpoint_schema_mismatch")

    def test_qdq_or_contract_tampering_is_rejected_not_reinterpreted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qdq = copy.deepcopy(self.qdq)
            qdq["receipt_sha256"] = "0" * 64
            qdq_path = root / "qdq.json"
            qdq_path.write_text(json.dumps(qdq), encoding="utf-8")
            with self.assertRaisesRegex(selector.ProfileSelectionError, "qdq_artifact_identity_mismatch"):
                selector.build_profile(CONTRACT, qdq_path)

    def test_self_rehashed_qdq_cannot_replace_pinned_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qdq = copy.deepcopy(self.qdq)
            qdq["profiles"][selector.PROFILE]["accumulation"]["synthesizable_rtl"]["logical_width_bits"] = 32
            qdq["receipt_sha256"] = selector.canonical_sha256({k: v for k, v in qdq.items() if k != "receipt_sha256"})
            qdq_path = root / "self-rehashed-qdq.json"
            qdq_path.write_text(json.dumps(qdq), encoding="utf-8")
            with self.assertRaisesRegex(selector.ProfileSelectionError, "qdq_artifact_identity_mismatch"):
                selector.build_profile(CONTRACT, qdq_path)


if __name__ == "__main__":
    unittest.main()
