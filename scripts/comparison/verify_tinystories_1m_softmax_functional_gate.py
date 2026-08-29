#!/usr/bin/env python3
"""Verify the functional-equivalence gate and fail closed without a trace."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _row_hash(row):
    return hashlib.sha256(json.dumps({k: v for k, v in row.items() if k != "sha256"}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _validated_reference_rows(reference: dict, base: dict) -> list[dict]:
    rows = reference.get("softmax_rows")
    if not isinstance(rows, list) or len(rows) != 16:
        base["comparison"]["first_missing_checkpoint"] = "reference_softmax_rows"
        base["comparison"]["blocking_artifact"] = {
            "path": "reference.softmax_rows",
            "reason": "reference_row_count_mismatch",
            "observed": None if not isinstance(rows, list) else len(rows),
        }
        return []
    for head, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("sha256") != _row_hash(row):
            base["comparison"]["first_missing_checkpoint"] = "reference_softmax_rows"
            base["comparison"]["blocking_artifact"] = {
                "path": "reference.softmax_rows",
                "reason": "reference_row_identity_mismatch",
                "head": head,
            }
            return []
    return rows


def _slice_metadata(reference: dict, base: dict) -> dict | None:
    slice_info = reference.get("slice")
    if not isinstance(slice_info, dict):
        base["comparison"]["first_missing_checkpoint"] = "reference_slice_metadata"
        base["comparison"]["blocking_artifact"] = {
            "path": "reference.slice",
            "reason": "reference_slice_missing",
        }
        return None
    prompt_tokens = slice_info.get("prompt_tokens")
    if (
        not isinstance(prompt_tokens, list)
        or any(not isinstance(token, int) or isinstance(token, bool) for token in prompt_tokens)
    ):
        base["comparison"]["first_missing_checkpoint"] = "reference_slice_metadata"
        base["comparison"]["blocking_artifact"] = {
            "path": "reference.slice",
            "reason": "reference_slice_field_missing" if "prompt_tokens" not in slice_info else "reference_slice_field_type_mismatch",
            "field": "prompt_tokens",
        }
        return None
    block_index = slice_info.get("block_index")
    if not isinstance(block_index, int) or isinstance(block_index, bool):
        base["comparison"]["first_missing_checkpoint"] = "reference_slice_metadata"
        base["comparison"]["blocking_artifact"] = {
            "path": "reference.slice",
            "reason": "reference_slice_field_missing" if "block_index" not in slice_info else "reference_slice_field_type_mismatch",
            "field": "block_index",
        }
        return None
    token_index = slice_info.get("token_index")
    if not isinstance(token_index, int) or isinstance(token_index, bool):
        base["comparison"]["first_missing_checkpoint"] = "reference_slice_metadata"
        base["comparison"]["blocking_artifact"] = {
            "path": "reference.slice",
            "reason": "reference_slice_field_missing" if "token_index" not in slice_info else "reference_slice_field_type_mismatch",
            "field": "token_index",
        }
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "block_index": block_index,
        "token_index": token_index,
    }


def _first_difference_index(expected, actual):
    if isinstance(expected, list) and isinstance(actual, list):
        limit = min(len(expected), len(actual))
        for index in range(limit):
            if expected[index] != actual[index]:
                nested = _first_difference_index(expected[index], actual[index])
                return [index, *nested]
        if len(expected) != len(actual):
            return [limit]
    return []

def evaluate_gate(gate_path: Path, oracle_path: Path, trace_path: Path, reference_path: Path) -> dict:
    gate = json.loads(Path(gate_path).read_text())
    oracle = json.loads(Path(oracle_path).read_text())
    reference = json.loads(Path(reference_path).read_text())
    if gate.get("schema") != "tinystories-1m-softmax-functional-equivalence-gate-v1":
        raise ValueError("gate_schema_mismatch")
    if gate.get("oracle", {}).get("sha256") != oracle.get("sha256"):
        raise ValueError("oracle_identity_mismatch")
    base = {"status": "fail_closed", "comparison": {"reference_row_count": 0, "matched_rows": 0, "first_missing_checkpoint": None, "first_mismatch": None}, "claims": {"functional_equivalence": False, "rtl_equivalence": False, "hardware_inference": False}}
    expected = _validated_reference_rows(reference, base)
    if not expected:
        return base
    base["comparison"]["reference_row_count"] = len(expected)
    expected_slice = _slice_metadata(reference, base)
    if expected_slice is None:
        return base
    trace = json.loads(Path(trace_path).read_text()) if Path(trace_path).is_file() else {}
    if trace.get("schema") != "tinystories-1m-compiler-fixed-softmax-trace-v1" or not isinstance(trace.get("rows"), list) or len(trace["rows"]) != len(expected):
        base["comparison"]["first_missing_checkpoint"] = "compiler_fixed_point_softmax_rows"
        base["comparison"]["blocking_artifact"] = {"path": str(trace_path), "reason": "fixed_rows_missing" if trace.get("schema") != "tinystories-1m-compiler-fixed-softmax-trace-v1" else "row_count_mismatch"}
        return base
    for field, expected_value in expected_slice.items():
        if trace.get(field) != expected_value:
            base["comparison"]["first_missing_checkpoint"] = "compiler_trace_metadata"
            base["comparison"]["blocking_artifact"] = {
                "path": str(trace_path),
                "reason": "metadata_mismatch",
                "field": field,
                "expected": expected_value,
                "observed": trace.get(field),
            }
            return base
    for head, (want, got) in enumerate(zip(expected, trace["rows"])):
        if not isinstance(got, dict) or got.get("sha256") != _row_hash(got):
            base["status"] = "mismatch"
            base["comparison"]["first_mismatch"] = {"head": head, "field": "row_sha256", "index": []}
            return base
        for field in ("score_codes_q8_8", "delta_codes_q8_8", "exp_q1_20", "probabilities_q1_20", "context_q16_16"):
            if got.get(field) != want.get(field):
                base["status"] = "mismatch"
                base["comparison"]["first_mismatch"] = {
                    "head": head,
                    "field": field,
                    "index": _first_difference_index(want.get(field), got.get(field)),
                }
                return base
    base["status"] = "matched"
    base["comparison"]["matched_rows"] = len(expected)
    base["claims"]["functional_equivalence"] = True
    return base

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", type=Path, required=True)
    ap.add_argument("--oracle", type=Path, required=True)
    ap.add_argument("--trace", type=Path)
    a = ap.parse_args()
    gate = json.loads(a.gate.read_text())
    oracle = json.loads(a.oracle.read_text())
    if gate.get("schema") != "tinystories-1m-softmax-functional-equivalence-gate-v1":
        raise SystemExit("gate_schema_mismatch")
    if gate["oracle"]["sha256"] != oracle.get("sha256"):
        raise SystemExit("oracle_identity_mismatch")
    if oracle.get("trace", {}).get("prompt_tokens") != gate["oracle"]["prompt_tokens"]:
        raise SystemExit("oracle_prompt_mismatch")
    if a.trace is None or not a.trace.is_file():
        print(json.dumps({"status": "fail_closed", "reason": "lowered_softmax_numeric_trace_missing", "functional_equivalence": False}, sort_keys=True))
        return 2
    result = evaluate_gate(a.gate, a.oracle, a.trace, Path("artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json"))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "matched" else 2

if __name__ == "__main__":
    raise SystemExit(main())
