#!/usr/bin/env python3
"""Compare compiler softmax traces with authenticated fixed-point rows.

This module deliberately does not convert floating-point values into a claimed
hardware trace.  Fixed-point equivalence requires the exact row fields emitted
by the authenticated reference artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "tinystories-1m-kev-gpt-fixed-conversion-trace-v1"
TRACE_SCHEMA = "tinystories-1m-compiler-fixed-softmax-trace-v1"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def row_sha256(row: Mapping[str, Any]) -> str:
    return canonical_sha256({k: v for k, v in row.items() if k != "sha256"})


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _fixed_rows(reference: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = reference.get("softmax_rows")
    if not isinstance(rows, list) or len(rows) != 16 or not all(isinstance(r, dict) for r in rows):
        raise ValueError("reference_fixed_rows_missing")
    for row in rows:
        if row.get("sha256") != row_sha256(row):
            raise ValueError("reference_row_hash_mismatch")
    return rows  # type: ignore[return-value]


def _slice_metadata(reference: Mapping[str, Any]) -> dict[str, Any]:
    slice_info = reference.get("slice")
    if not isinstance(slice_info, dict):
        raise ValueError("reference_slice_missing")
    for key in ("prompt_tokens", "block_index", "token_index"):
        if key not in slice_info:
            raise ValueError(f"reference_slice_field_missing:{key}")
    return {
        "prompt_tokens": slice_info["prompt_tokens"],
        "block_index": slice_info["block_index"],
        "token_index": slice_info["token_index"],
    }


def _first_difference_index(expected: Any, actual: Any) -> list[int]:
    if isinstance(expected, list) and isinstance(actual, list):
        limit = min(len(expected), len(actual))
        for index in range(limit):
            if expected[index] != actual[index]:
                nested = _first_difference_index(expected[index], actual[index])
                return [index, *nested]
        if len(expected) != len(actual):
            return [limit]
        return []
    return []


def _base(reference: Mapping[str, Any], status: str) -> dict[str, Any]:
    slice_info = reference.get("slice", {})
    rows = _fixed_rows(reference)
    return {
        "schema": SCHEMA,
        "status": status,
        "reference": {
            "path": "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json",
            "slice": slice_info,
            "row_count": len(rows),
        },
        "comparison": {
            "reference_row_count": len(rows),
            "matched_rows": 0,
            "first_missing_checkpoint": None,
            "first_mismatch": None,
        },
        "claims": {
            "functional_equivalence": False,
            "rtl_equivalence": False,
            "hardware_inference": False,
        },
    }


def build_report(trace_path: Path, profile_path: Path, reference_path: Path) -> dict[str, Any]:
    del profile_path  # profile identity is carried by the authenticated reference artifact.
    trace = _load(trace_path)
    reference = _load(reference_path)
    report = _base(reference, "fail_closed")
    rows = _fixed_rows(reference)
    expected_slice = _slice_metadata(reference)
    if trace.get("schema") != TRACE_SCHEMA or not isinstance(trace.get("rows"), list):
        report["comparison"]["first_missing_checkpoint"] = "compiler_fixed_point_softmax_rows"
        report["comparison"]["blocking_artifact"] = {"path": str(trace_path), "reason": "fixed_rows_missing"}
        return report
    for field, expected_value in expected_slice.items():
        if trace.get(field) != expected_value:
            report["comparison"]["first_missing_checkpoint"] = "compiler_trace_metadata"
            report["comparison"]["blocking_artifact"] = {
                "path": str(trace_path),
                "reason": "metadata_mismatch",
                "field": field,
                "expected": expected_value,
                "observed": trace.get(field),
            }
            return report
    candidate = trace["rows"]
    if len(candidate) != len(rows):
        report["comparison"]["first_missing_checkpoint"] = "compiler_fixed_point_softmax_rows"
        report["comparison"]["blocking_artifact"] = {"path": str(trace_path), "reason": "row_count_mismatch"}
        return report
    for head, (expected, actual) in enumerate(zip(rows, candidate)):
        if not isinstance(actual, dict) or actual.get("sha256") != row_sha256(actual):
            report["status"] = "mismatch"
            report["comparison"]["first_mismatch"] = {"head": head, "field": "row_sha256", "index": []}
            return report
        for field in ("score_codes_q8_8", "delta_codes_q8_8", "exp_q1_20", "probabilities_q1_20", "context_q16_16"):
            if actual.get(field) != expected.get(field):
                report["status"] = "mismatch"
                report["comparison"]["first_mismatch"] = {
                    "head": head,
                    "field": field,
                    "index": _first_difference_index(expected.get(field), actual.get(field)),
                }
                return report
    report["status"] = "matched"
    report["comparison"]["matched_rows"] = len(rows)
    report["claims"]["functional_equivalence"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.trace, args.profile, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
