#!/usr/bin/env python3
"""Select the TinyStories-1M numeric implementation profile, fail closed.

The frozen Task-1 contract is retained as historical source identity.  It
describes INT32/per-tensor semantics which conflict with the authenticated
fixed-point reference/RTL.  A compiler comparison may use the fixed profile
only after a content-bound YPCB execution receipt reproduces its complete
block-0 checkpoint trace and frozen 16-token output.

This tool does not execute, copy, or modify the AGPL reference.  It consumes
the already authenticated Q/DQ receipt and a separately captured board receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "tinystories-1m-implementation-profile-v1"
BOARD_SCHEMA = "tinystories-1m-board-checkpoint-receipt-v1"
QDQ_SCHEMA = "tinystories-1m-qdq-semantics-v1"
PROFILE = "fixed_hardware_reference"


class ProfileSelectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def profile_sha256(profile: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in profile.items() if key != "profile_sha256"})


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileSelectionError("invalid_json", f"{label}: {error}") from error
    if not isinstance(value, dict):
        raise ProfileSelectionError("invalid_json", f"{label} must be an object")
    return value


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ProfileSelectionError(code, message)


def _validate_qdq(receipt: dict[str, Any], qdq_path: Path, contract_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _require(receipt.get("schema") == QDQ_SCHEMA, "qdq_schema_mismatch", str(qdq_path))
    _require(receipt.get("receipt_sha256") == canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    ), "qdq_receipt_hash_mismatch", str(qdq_path))
    identity = receipt.get("identity")
    profiles = receipt.get("profiles")
    oracle = receipt.get("candidate_oracle")
    _require(isinstance(identity, dict) and isinstance(profiles, dict) and isinstance(oracle, dict),
             "qdq_schema_mismatch", "missing identity/profiles/candidate_oracle")
    _require(identity.get("contract_sha256") == sha256_file(contract_path),
             "contract_identity_mismatch", "Q/DQ receipt is not bound to the frozen contract")
    fixed = profiles.get(PROFILE)
    _require(isinstance(fixed, dict), "fixed_profile_missing", PROFILE)
    _require(oracle.get("status") == "runtime_authenticated_not_board_checkpoint_authenticated",
             "qdq_oracle_status_mismatch", "candidate oracle status is not explicit")
    _require(oracle.get("sha256") == canonical_sha256(
        {key: value for key, value in oracle.items() if key != "sha256"}
    ), "oracle_hash_mismatch", "candidate oracle")
    return fixed, oracle


def _validate_board_evidence(
    board: dict[str, Any],
    *,
    qdq_path: Path,
    qdq: dict[str, Any],
    contract_path: Path,
    contract: dict[str, Any],
    oracle: dict[str, Any],
) -> dict[str, Any]:
    """Authenticate a future board receipt sufficiently to select the profile."""

    _require(board.get("schema") == BOARD_SCHEMA, "board_schema_mismatch", "unexpected board schema")
    required = {
        "schema", "profile", "contract_sha256", "qdq_receipt_sha256", "board", "bitstream_sha256",
        "source_hashes", "prompt_tokens", "output_tokens", "trace", "receipt_sha256",
    }
    _require(set(board) == required, "board_schema_mismatch", "board receipt keys are not exact")
    _require(board.get("receipt_sha256") == canonical_sha256(
        {key: value for key, value in board.items() if key != "receipt_sha256"}
    ), "board_receipt_hash_mismatch", "board receipt")
    _require(board.get("profile") == PROFILE, "board_profile_mismatch", str(board.get("profile")))
    _require(board.get("contract_sha256") == sha256_file(contract_path),
             "board_contract_mismatch", "board receipt contract hash differs")
    _require(board.get("qdq_receipt_sha256") == qdq.get("receipt_sha256"),
             "board_qdq_mismatch", "board receipt Q/DQ receipt hash differs")
    _require(isinstance(board.get("board"), dict) and board["board"].get("name") == "YPCB-00338-1P1",
             "board_identity_mismatch", "expected YPCB-00338-1P1")
    _require(_sha256(board.get("bitstream_sha256")), "board_bitstream_identity_missing", "bitstream SHA-256")
    source_hashes = board.get("source_hashes")
    authority = qdq.get("authority")
    _require(isinstance(source_hashes, dict) and isinstance(authority, dict), "board_source_identity_missing", "source hashes")
    expected_sources = {item["path"]: item["sha256"] for item in authority.get("sources", []) if isinstance(item, dict)}
    _require(source_hashes == expected_sources, "board_source_identity_mismatch", "board source hashes differ")
    _require(board.get("prompt_tokens") == contract.get("reference", {}).get("prompt_tokens"),
             "board_prompt_mismatch", "board prompt differs")
    _require(board.get("output_tokens") == contract.get("reference", {}).get("tokens"),
             "board_output_mismatch", "board output differs")
    trace = board.get("trace")
    expected_trace = {
        "block_index": oracle.get("block_index"),
        "checkpoint_order": oracle.get("checkpoint_order"),
        "checkpoints": oracle.get("checkpoints"),
        "sha256": oracle.get("sha256"),
    }
    _require(trace == expected_trace, "board_trace_mismatch", "board trace differs from fixed-point oracle")
    return {
        "path": str(qdq_path),
        "board": board["board"],
        "bitstream_sha256": board["bitstream_sha256"],
        "receipt_sha256": board["receipt_sha256"],
        "trace_sha256": trace["sha256"],
    }


def build_profile(contract_path: Path, qdq_path: Path, board_path: Path | None = None) -> dict[str, Any]:
    contract = _load_object(contract_path, "contract")
    qdq = _load_object(qdq_path, "Q/DQ receipt")
    fixed, oracle = _validate_qdq(qdq, qdq_path, contract_path)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "version": 1,
        "status": "unresolved",
        "selected_profile": None,
        "identity": {
            "contract_sha256": sha256_file(contract_path),
            "qdq_receipt_sha256": qdq["receipt_sha256"],
            "qdq_receipt_path": str(qdq_path),
        },
        "candidate_profile": {
            "name": PROFILE,
            "semantics": fixed,
            "runtime_oracle_sha256": oracle["sha256"],
        },
        "supersession": {
            "source_contract_retained": True,
            "would_supersede_only_if_board_selected": {
                "accumulator": {"source_contract": "signed INT32", "candidate": "signed INT64 serial RTL"},
                "activation_scales": {"source_contract": "per-tensor INT8", "candidate": "per-channel Q8.24"},
                "rounding": {"source_contract": "unspecified", "candidate": "ties-away-from-zero at activation/requantize"},
                "clamp": {"source_contract": "unspecified", "candidate": [-128, 127]},
            },
        },
        "board_evidence": None,
        "unresolved_reasons": [],
    }
    if board_path is None:
        result["unresolved_reasons"] = [{
            "code": "board_checkpoint_receipt_missing",
            "missing_artifact": "A content-bound YPCB-00338-1P1 TinyStories-1M receipt with the exact fixed-profile source hashes, bitstream hash, frozen prompt/output, and all 12 block-0 checkpoint tensors.",
            "not_accepted_as_substitute": "The existing kintex self-test provenance proves only a self-test image and cannot authenticate TinyStories inference semantics.",
        }]
    else:
        board = _load_object(board_path, "board receipt")
        try:
            result["board_evidence"] = _validate_board_evidence(
                board, qdq_path=qdq_path, qdq=qdq, contract_path=contract_path, contract=contract, oracle=oracle
            )
        except ProfileSelectionError as error:
            result["unresolved_reasons"] = [{"code": error.code, "missing_or_conflicting_evidence": str(error)}]
        else:
            result["status"] = "selected"
            result["selected_profile"] = PROFILE
    result["profile_sha256"] = profile_sha256(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--qdq-receipt", required=True, type=Path)
    parser.add_argument("--board-receipt", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    profile = build_profile(args.contract, args.qdq_receipt, args.board_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
