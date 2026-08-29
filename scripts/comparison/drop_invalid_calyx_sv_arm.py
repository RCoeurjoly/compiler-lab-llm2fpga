#!/usr/bin/env python3
"""Experimental, source-aware removal of one invalid native-Calyx mux arm.

This never rewrites an in-tree generated RTL file.  It is constrained to one
complete OR-term in the first condition of one continuous assignment and is
intended only to test a binding-audit finding against the exact harness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def drop_or_guard_term(source: str, assignment: str, guard: str) -> tuple[str, dict[str, object]]:
    match = re.search(
        rf"\bassign\s+{re.escape(assignment)}\s*=\s*(?P<rhs>.*?);",
        source,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError(f"missing assignment for {assignment}")
    rhs = match.group("rhs")
    if "?" not in rhs:
        raise ValueError(f"assignment {assignment} has no mux arm")
    condition, remainder = rhs.split("?", 1)
    terms = [term.strip() for term in condition.split("|")]
    occurrences = terms.count(guard)
    if occurrences != 1:
        raise ValueError(
            f"guard {guard} must occur exactly once as a complete OR term; found {occurrences}"
        )
    retained = [term for term in terms if term != guard]
    if not retained:
        raise ValueError("refusing to remove the only mux guard")
    rewritten_rhs = " | ".join(retained) + " ?" + remainder
    rewritten = source[: match.start("rhs")] + rewritten_rhs + source[match.end("rhs") :]
    return rewritten, {
        "assignment": assignment,
        "guard": guard,
        "removed_arms": 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--assignment", required=True)
    parser.add_argument("--guard", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    original = args.input.read_text(encoding="utf-8")
    rewritten, receipt = drop_or_guard_term(original, args.assignment, args.guard)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rewritten, encoding="utf-8")
    receipt.update(
        {
            "schema": "calyx-invalid-mux-arm-experiment-v1",
            "input": str(args.input),
            "output": str(args.output),
            "input_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "output_sha256": hashlib.sha256(rewritten.encode()).hexdigest(),
            "scope": {"production_rtl_changed": False, "experimental_only": True},
        }
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
