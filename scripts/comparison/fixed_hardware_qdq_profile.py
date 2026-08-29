#!/usr/bin/env python3
"""Create and verify the runtime-authenticated TinyStories fixed-Q/DQ profile.

This is a compiler-input profile, not a board-selection receipt.  It consumes
the already authenticated Task 3g semantics receipt and records only semantic
rules and the deterministic fixed-runtime trace that receipt proves.  It never
imports, copies, or emits kev-gpt source or RTL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "tinystories-1m-fixed-hardware-qdq-profile-v1"
VERSION = 1
QDQ_SCHEMA = "tinystories-1m-qdq-semantics-v1"
PROFILE_NAME = "fixed_hardware_reference"
CANONICAL_CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
CANONICAL_QDQ_ARTIFACT_SHA256 = "a274d61ec5f634fac8fb501339ddfe7ae4bf774d950840498d54c32b90d79e77"
CANONICAL_QDQ_RECEIPT_SHA256 = "c025c8e89ba71dca2437b89f90105d9cc5fd44366e5b51ef089288d15fde730f"
CHECKPOINT_SHAPES: dict[str, tuple[int, ...]] = {
    "block.input": (64,), "block.ln_1.output": (64,), "block.attention.q": (16, 4),
    "block.attention.k": (16, 4), "block.attention.v": (16, 4),
    "block.attention.output": (64,), "block.residual.attention": (64,),
    "block.ln_2.output": (64,), "block.mlp.fc_in": (256,), "block.mlp.activation": (256,),
    "block.mlp.fc_out": (64,), "block.output": (64,),
}


class FixedHardwareProfileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def profile_sha256(profile: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in profile.items() if key != "profile_sha256"})


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise FixedHardwareProfileError(code, message)


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FixedHardwareProfileError("invalid_json", f"{label}: {error}") from error
    _require(isinstance(value, dict), "invalid_json", f"{label} must be an object")
    return value


def _strict_int_tree(value: Any) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, list) and all(_strict_int_tree(item) for item in value)
    )


def _validate_trace(oracle: Any) -> dict[str, Any]:
    _require(isinstance(oracle, dict), "software_trace_schema_mismatch", "candidate oracle missing")
    required = {"status", "profile", "block_index", "token_index", "prompt_tokens", "next_token", "checkpoint_order", "checkpoints", "sha256"}
    _require(set(oracle) == required, "software_trace_schema_mismatch", "candidate oracle keys")
    _require(oracle["status"] == "runtime_authenticated_not_board_checkpoint_authenticated",
             "software_trace_status_mismatch", "runtime-only status is required")
    _require(oracle["profile"] == PROFILE_NAME, "software_trace_profile_mismatch", "wrong trace profile")
    _require(oracle["block_index"] == 0 and oracle["token_index"] == 3,
             "software_trace_context_mismatch", "expected block-0, final prompt token")
    _require(oracle["prompt_tokens"] == [7454, 2402, 257, 640] and oracle["next_token"] == 11,
             "software_trace_token_mismatch", "fixed runtime token step differs")
    _require(oracle["checkpoint_order"] == list(CHECKPOINT_SHAPES), "software_trace_checkpoint_order_mismatch", "wrong checkpoint order")
    checkpoints = oracle["checkpoints"]
    _require(isinstance(checkpoints, dict) and set(checkpoints) == set(CHECKPOINT_SHAPES),
             "software_trace_checkpoint_coverage_mismatch", "expected exactly twelve checkpoints")
    for name, shape in CHECKPOINT_SHAPES.items():
        checkpoint = checkpoints[name]
        _require(isinstance(checkpoint, dict) and set(checkpoint) == {"shape", "dtype", "values", "sha256"},
                 "software_trace_checkpoint_schema_mismatch", name)
        payload = {"shape": list(shape), "dtype": "signed_q16.16", "values": checkpoint.get("values")}
        _require(checkpoint.get("shape") == list(shape) and checkpoint.get("dtype") == "signed_q16.16" and _strict_int_tree(checkpoint.get("values")),
                 "software_trace_checkpoint_schema_mismatch", name)
        _require(checkpoint.get("sha256") == canonical_sha256(payload), "software_trace_checkpoint_hash_mismatch", name)
    expected_hash = canonical_sha256({key: value for key, value in oracle.items() if key != "sha256"})
    _require(oracle["sha256"] == expected_hash and re.fullmatch(r"[0-9a-f]{64}", oracle["sha256"]) is not None,
             "software_trace_hash_mismatch", "candidate trace hash")
    return oracle


def _validate_semantics(value: Any) -> dict[str, Any]:
    _require(isinstance(value, dict), "fixed_semantics_missing", PROFILE_NAME)
    activation = value.get("activation_conversion")
    accumulation = value.get("accumulation")
    weight = value.get("weight_scale")
    boundaries = value.get("activation_boundaries")
    _require(isinstance(activation, dict) and activation == {
        "input": "signed_q16.16_int32", "scale": "per-channel_unsigned_q8.24_u24",
        "rounding": "nearest_ties_away_from_zero", "clamp": [-128, 127], "zero_point": 0,
        "dequantization": "signed_int8_code_times_q8.24_scale_then_signed_half_away_shift_by_8",
        "result": "signed_q16.16_int32",
    }, "activation_semantics_mismatch", "Q8.24 activation Q/DQ semantics")
    _require(isinstance(accumulation, dict) and accumulation.get("term") == "activation_code_i_times_activation_scale_q24_i_times_weight_code_output_i",
             "accumulation_semantics_mismatch", "MAC term")
    _require(accumulation.get("synthesizable_rtl") == {
        "operation": "serial_multiply_accumulate", "input_order": "ascending_input_index",
        "logical_width_bits": 64, "overflow": "twos_complement_wrap",
    }, "accumulation_semantics_mismatch", "serial signed-64 RTL semantics")
    _require(isinstance(weight, dict) and weight == {
        "axis": "output_channel", "application": "signed_int64_accumulator_times_unsigned_q8.24_scale",
        "rounding": "nearest_ties_away_from_zero_by_signed_shift_32",
        "bias_order": "add_signed_q16.16_bias_after_weight_scale",
    }, "weight_scale_semantics_mismatch", "per-output scale/bias semantics")
    _require(isinstance(boundaries, dict) and boundaries.get("count") == 97 and boundaries.get("widths") == [64, 256]
             and boundaries.get("scale_interpretation") == "one positive scale per last-dimension channel",
             "activation_boundary_semantics_mismatch", "97 per-channel boundaries")
    _require(value.get("execution_domain") == "integers_only_after_materialization",
             "execution_domain_mismatch", "fixed integer execution domain")
    return value


def _validated_qdq(contract_path: Path, qdq_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _require(sha256_file(contract_path) == CANONICAL_CONTRACT_SHA256,
             "contract_artifact_identity_mismatch", str(contract_path))
    _require(sha256_file(qdq_path) == CANONICAL_QDQ_ARTIFACT_SHA256,
             "qdq_artifact_identity_mismatch", str(qdq_path))
    receipt = _load(qdq_path, "Q/DQ receipt")
    _require(receipt.get("schema") == QDQ_SCHEMA, "qdq_schema_mismatch", "schema")
    _require(receipt.get("receipt_sha256") == canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"}),
             "qdq_receipt_hash_mismatch", "self hash")
    _require(receipt.get("receipt_sha256") == CANONICAL_QDQ_RECEIPT_SHA256,
             "qdq_receipt_identity_mismatch", "canonical receipt identity")
    identity = receipt.get("identity")
    _require(isinstance(identity, dict) and identity.get("contract_sha256") == CANONICAL_CONTRACT_SHA256,
             "contract_identity_mismatch", "receipt contract binding")
    profiles = receipt.get("profiles")
    _require(isinstance(profiles, dict), "fixed_semantics_missing", "profiles")
    return receipt, _validate_semantics(profiles.get(PROFILE_NAME)), _validate_trace(receipt.get("candidate_oracle"))


def build_profile(contract_path: Path, qdq_path: Path) -> dict[str, Any]:
    receipt, semantics, trace = _validated_qdq(Path(contract_path), Path(qdq_path))
    profile: dict[str, Any] = {
        "schema": SCHEMA, "version": VERSION,
        "status": "runtime_authenticated_not_board_checkpoint_authenticated",
        "profile": PROFILE_NAME, "board_authenticated": False,
        "identity": {
            "contract_sha256": CANONICAL_CONTRACT_SHA256,
            "qdq_artifact_sha256": sha256_file(Path(qdq_path)),
            "qdq_receipt_sha256": receipt["receipt_sha256"],
        },
        "semantics": semantics,
        "software_trace": trace,
        "unresolved_board_authority": {
            "code": "board_checkpoint_receipt_missing",
            "required": "A content-bound YPCB TinyStories-1M board receipt selecting this profile and reproducing all twelve checkpoints.",
        },
    }
    profile["profile_sha256"] = profile_sha256(profile)
    return profile


def validate_profile(profile_path: Path, contract_path: Path, qdq_path: Path) -> dict[str, Any]:
    expected = build_profile(contract_path, qdq_path)
    profile = _load(Path(profile_path), "fixed-hardware Q/DQ profile")
    _require(profile == expected, "profile_content_mismatch", "profile differs from canonical authenticated semantics receipt")
    _require(profile.get("profile_sha256") == profile_sha256(profile), "profile_hash_mismatch", "self hash")
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--qdq-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        validate_profile(args.output, args.contract, args.qdq_receipt)
        return
    profile = build_profile(args.contract, args.qdq_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
