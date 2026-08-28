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
CAPTURE_SCHEMA = "tinystories-1m-board-checkpoint-capture-v1"
BITSTREAM_MANIFEST_SCHEMA = "tinystories-1m-board-bitstream-manifest-v1"
QDQ_SCHEMA = "tinystories-1m-qdq-semantics-v1"
PROFILE = "fixed_hardware_reference"
CANONICAL_QDQ_ARTIFACT_SHA256 = "a274d61ec5f634fac8fb501339ddfe7ae4bf774d950840498d54c32b90d79e77"
CANONICAL_QDQ_RECEIPT_SHA256 = "c025c8e89ba71dca2437b89f90105d9cc5fd44366e5b51ef089288d15fde730f"
CANONICAL_CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"

# This registry is deliberately source-controlled rather than supplied by a
# receipt.  Adding an entry is an evidence-review change: it must name the
# exact board-receipt file digest and its two independently existing artifacts.
# It is empty until a real YPCB TinyStories capture is preserved and reviewed.
APPROVED_BOARD_RECEIPTS: dict[str, dict[str, str]] = {}


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
    _require(sha256_file(qdq_path) == CANONICAL_QDQ_ARTIFACT_SHA256,
             "qdq_artifact_identity_mismatch", str(qdq_path))
    _require(sha256_file(contract_path) == CANONICAL_CONTRACT_SHA256,
             "contract_artifact_identity_mismatch", str(contract_path))
    _require(receipt.get("schema") == QDQ_SCHEMA, "qdq_schema_mismatch", str(qdq_path))
    _require(receipt.get("receipt_sha256") == canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    ), "qdq_receipt_hash_mismatch", str(qdq_path))
    _require(receipt.get("receipt_sha256") == CANONICAL_QDQ_RECEIPT_SHA256,
             "qdq_receipt_identity_mismatch", str(qdq_path))
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


def _file_matches(path_value: Any, digest: Any, code: str, label: str) -> Path:
    _require(isinstance(path_value, str) and bool(path_value) and _sha256(digest), code, label)
    path = Path(path_value)
    try:
        _require(path.is_file() and sha256_file(path) == digest, code, label)
    except OSError as error:
        raise ProfileSelectionError(code, f"{label}: {error}") from error
    return path


def _strict_integer_tree(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, list):
        return all(_strict_integer_tree(item) for item in value)
    return False


def _validate_trace(trace: Any, oracle: Mapping[str, Any]) -> None:
    _require(isinstance(trace, dict) and set(trace) == {"block_index", "checkpoint_order", "checkpoints", "sha256"},
             "board_trace_schema_mismatch", "trace keys")
    _require(isinstance(trace.get("block_index"), int) and not isinstance(trace.get("block_index"), bool),
             "board_trace_schema_mismatch", "block index")
    order = trace.get("checkpoint_order")
    checkpoints = trace.get("checkpoints")
    _require(isinstance(order, list) and all(isinstance(name, str) for name in order) and isinstance(checkpoints, dict),
             "board_trace_schema_mismatch", "trace order/checkpoints")
    _require(set(checkpoints) == set(order), "board_trace_schema_mismatch", "checkpoint coverage")
    for name in order:
        checkpoint = checkpoints.get(name)
        _require(isinstance(checkpoint, dict) and set(checkpoint) == {"shape", "dtype", "values", "sha256"},
                 "board_checkpoint_schema_mismatch", str(name))
        shape = checkpoint.get("shape")
        values = checkpoint.get("values")
        _require(isinstance(shape, list) and shape and all(isinstance(dim, int) and not isinstance(dim, bool) and dim > 0 for dim in shape),
                 "board_checkpoint_schema_mismatch", f"{name}.shape")
        _require(isinstance(checkpoint.get("dtype"), str) and _strict_integer_tree(values),
                 "board_checkpoint_schema_mismatch", f"{name}.dtype/values")
        _require(checkpoint.get("sha256") == canonical_sha256({"shape": shape, "dtype": checkpoint["dtype"], "values": values}),
                 "board_checkpoint_hash_mismatch", name)
    _require(trace.get("sha256") == canonical_sha256({
        "block_index": trace["block_index"], "checkpoint_order": order, "checkpoints": checkpoints
    }), "board_trace_hash_mismatch", "trace")
    expected_trace_content = {key: oracle.get(key) for key in ("block_index", "checkpoint_order", "checkpoints")}
    observed_trace_content = {key: trace.get(key) for key in ("block_index", "checkpoint_order", "checkpoints")}
    _require(canonical_sha256(observed_trace_content) == canonical_sha256(expected_trace_content),
             "board_trace_mismatch", "board trace differs from fixed-point oracle")


def _validate_board_evidence(
    board: dict[str, Any],
    *,
    board_path: Path,
    qdq: dict[str, Any],
    contract_path: Path,
    contract: dict[str, Any],
    oracle: dict[str, Any],
) -> dict[str, Any]:
    """Authenticate a future board receipt sufficiently to select the profile."""

    _require(board.get("schema") == BOARD_SCHEMA, "board_schema_mismatch", "unexpected board schema")
    required = {"schema", "profile", "contract_sha256", "qdq_receipt_sha256", "board", "bitstream",
                "source_hashes", "capture", "receipt_sha256"}
    _require(set(board) == required, "board_schema_mismatch", "board receipt keys are not exact")
    _require(board.get("receipt_sha256") == canonical_sha256(
        {key: value for key, value in board.items() if key != "receipt_sha256"}
    ), "board_receipt_hash_mismatch", "board receipt")
    board_file_sha256 = sha256_file(board_path)
    approval = APPROVED_BOARD_RECEIPTS.get(board_file_sha256)
    _require(isinstance(approval, dict), "board_receipt_not_approved",
             "board receipt bytes are not in the source-controlled approval registry")
    _require(board.get("profile") == PROFILE, "board_profile_mismatch", str(board.get("profile")))
    _require(board.get("contract_sha256") == CANONICAL_CONTRACT_SHA256,
             "board_contract_mismatch", "board receipt contract hash differs")
    _require(board.get("qdq_receipt_sha256") == CANONICAL_QDQ_RECEIPT_SHA256,
             "board_qdq_mismatch", "board receipt Q/DQ receipt hash differs")
    _require(isinstance(board.get("board"), dict) and board["board"].get("name") == "YPCB-00338-1P1",
             "board_identity_mismatch", "expected YPCB-00338-1P1")
    bitstream = board.get("bitstream")
    _require(isinstance(bitstream, dict) and set(bitstream) == {"path", "sha256", "manifest_path", "manifest_sha256"},
             "board_bitstream_identity_missing", "bitstream path/manifest/SHA-256")
    _file_matches(bitstream.get("path"), bitstream.get("sha256"), "board_bitstream_identity_mismatch", "bitstream")
    manifest_path = _file_matches(bitstream.get("manifest_path"), bitstream.get("manifest_sha256"),
                                  "board_bitstream_manifest_identity_mismatch", "bitstream manifest")
    manifest = _load_object(manifest_path, "bitstream manifest")
    _require(set(manifest) == {"schema", "bitstream_path", "bitstream_sha256", "build_provenance"}
             and manifest.get("schema") == BITSTREAM_MANIFEST_SCHEMA
             and manifest.get("bitstream_path") == bitstream.get("path")
             and manifest.get("bitstream_sha256") == bitstream.get("sha256")
             and isinstance(manifest.get("build_provenance"), dict),
             "board_bitstream_manifest_schema_mismatch", "manifest binding")
    _require(approval.get("bitstream_sha256") == bitstream.get("sha256"),
             "board_approval_mismatch", "approved bitstream hash differs")
    source_hashes = board.get("source_hashes")
    authority = qdq.get("authority")
    _require(isinstance(source_hashes, dict) and isinstance(authority, dict), "board_source_identity_missing", "source hashes")
    expected_sources = {item["path"]: item["sha256"] for item in authority.get("sources", []) if isinstance(item, dict)}
    _require(source_hashes == expected_sources, "board_source_identity_mismatch", "board source hashes differ")
    capture_ref = board.get("capture")
    _require(isinstance(capture_ref, dict) and set(capture_ref) == {
        "path", "sha256", "transcript_path", "transcript_sha256", "tool_path", "tool_sha256", "protocol_path", "protocol_sha256"
    }, "board_capture_identity_missing", "capture/transcript/tool/protocol paths and SHA-256")
    capture_path = _file_matches(capture_ref.get("path"), capture_ref.get("sha256"),
                                 "board_capture_identity_mismatch", "board capture")
    _require(approval.get("capture_sha256") == capture_ref.get("sha256"),
             "board_approval_mismatch", "approved capture hash differs")
    _file_matches(capture_ref.get("transcript_path"), capture_ref.get("transcript_sha256"),
                  "board_transcript_identity_mismatch", "raw board transcript")
    _file_matches(capture_ref.get("tool_path"), capture_ref.get("tool_sha256"),
                  "board_capture_tool_identity_mismatch", "capture tool")
    _file_matches(capture_ref.get("protocol_path"), capture_ref.get("protocol_sha256"),
                  "board_capture_protocol_identity_mismatch", "capture protocol")
    capture = _load_object(capture_path, "board capture")
    expected_capture_keys = {"schema", "capture_method", "board", "bitstream_sha256", "prompt_tokens",
                             "output_tokens", "trace"}
    _require(set(capture) == expected_capture_keys and capture.get("schema") == CAPTURE_SCHEMA,
             "board_capture_schema_mismatch", "capture keys/schema")
    _require(capture.get("capture_method") == "board_debug_csr_readback",
             "board_capture_not_explicit", "expected board debug-CSR readback capture")
    _require(capture.get("board") == board.get("board"), "board_capture_identity_mismatch", "board identity")
    _require(capture.get("bitstream_sha256") == bitstream.get("sha256"),
             "board_capture_identity_mismatch", "bitstream hash")
    _require(capture.get("prompt_tokens") == contract.get("reference", {}).get("prompt_tokens"),
             "board_prompt_mismatch", "board prompt differs")
    _require(capture.get("output_tokens") == contract.get("reference", {}).get("tokens"),
             "board_output_mismatch", "board output differs")
    trace = capture.get("trace")
    _validate_trace(trace, oracle)
    return {
        "path": str(board_path),
        "sha256": board_file_sha256,
        "board": board["board"],
        "bitstream_path": bitstream["path"],
        "bitstream_sha256": bitstream["sha256"],
        "bitstream_manifest_path": str(manifest_path),
        "bitstream_manifest_sha256": bitstream["manifest_sha256"],
        "capture_path": str(capture_path),
        "capture_sha256": capture_ref["sha256"],
        "transcript_path": capture_ref["transcript_path"],
        "transcript_sha256": capture_ref["transcript_sha256"],
        "tool_path": capture_ref["tool_path"],
        "tool_sha256": capture_ref["tool_sha256"],
        "protocol_path": capture_ref["protocol_path"],
        "protocol_sha256": capture_ref["protocol_sha256"],
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
        try:
            board = _load_object(board_path, "board receipt")
            result["board_evidence"] = _validate_board_evidence(
                board, board_path=board_path, qdq=qdq, contract_path=contract_path, contract=contract, oracle=oracle
            )
        except ProfileSelectionError as error:
            result["unresolved_reasons"] = [{"code": error.code, "missing_or_conflicting_evidence": str(error)}]
        except (OSError, TypeError, ValueError) as error:
            # Malformed JSON (including NaN, which Python's parser otherwise
            # accepts) is board evidence failure, never a selector crash.
            result["unresolved_reasons"] = [{
                "code": "board_evidence_invalid",
                "missing_or_conflicting_evidence": f"board evidence validation failed: {type(error).__name__}",
            }]
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
