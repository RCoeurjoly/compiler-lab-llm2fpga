#!/usr/bin/env python3
"""Independently replay the kev-gpt fixed-point attention softmax rows."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
from typing import Any

Q = 1 << 20

def replay(reference: dict[str, Any]) -> dict[str, Any]:
    rows = reference.get("softmax_rows", [])
    checked = 0
    mismatches = []
    for row in rows:
        scores = row["score_codes_q8_8"]
        maximum = max(scores)
        delta = [max(-4096, min(0, s - maximum)) for s in scores]
        indices = [None if d == 0 else 4096 + d for d in delta]
        exp = [Q if i is None else int(math.exp((i - 4096) / 256.0) * Q + 0.5) for i in indices]
        denominator = sum(exp)
        probabilities = [(e * Q) // denominator for e in exp]
        expected = (row["max_score_code_q8_8"], row["delta_codes_q8_8"], row["exp_lut_indices"], row["exp_q1_20"], row["denominator_q1_20"], row["probabilities_q1_20"])
        actual = (maximum, delta, indices, exp, denominator, probabilities)
        if actual != expected:
            mismatches.append({"head": row.get("head"), "expected": expected, "actual": actual})
        checked += 1
    return {"schema": "tinystories-1m-fixed-softmax-independent-replay-v1",
            "status": "pass" if not mismatches and checked == 16 else "fail",
            "rows_checked": checked, "mismatches": mismatches,
            "contract": {"heads": 16, "lut_entries": 4096, "lut_rounding": "nearest", "probability_rounding": "floor"},
            "claims": {"fixed_softmax_contract_replayed": not mismatches and checked == 16,
                       "compiler_equivalence": False, "hardware_inference": False}}

def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--reference", type=Path, required=True); ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    ref = json.loads(args.reference.read_text(encoding="utf-8"))
    result = replay(ref)
    result["reference_sha256"] = hashlib.sha256(json.dumps(ref, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raise SystemExit(0 if result["status"] == "pass" else 1)
if __name__ == "__main__": main()
