#!/usr/bin/env python3
"""Rewrite one proven Calyx memory-write mux into a parallel case selector.

The RC's measured critical cone is the generated ``arg_mem_59_write_data``
selector.  Its guards are disjoint scheduled basic-block enables (each is
controlled by a distinct FSM state), so a parallel case preserves the RTL
behavior for the hardware-valid 0/1 domain while giving synthesis an
explicitly non-priority structure.  This is an opt-in diagnostic pass, not a
general SV rewriter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


TARGET = "arg_mem_59_write_data"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rewrite(source: str) -> tuple[str, int]:
    pattern = re.compile(
        rf"assign\s+{TARGET}\s*=\s*(?P<body>.*?);", re.DOTALL
    )
    match = pattern.search(source)
    if match is None:
        raise ValueError(f"missing generated {TARGET} assignment")
    body = match.group("body")
    branches = []
    cursor = 0
    branch_re = re.compile(r"(?P<guard>.*?)\?\s*(?P<value>[A-Za-z0-9_]+)\s*:", re.DOTALL)
    for branch in branch_re.finditer(body):
        if branch.start() != cursor:
            # Permit whitespace between branches, but reject an unexpected
            # expression so the pass cannot silently change semantics.
            if body[cursor:branch.start()].strip():
                raise ValueError("unexpected text in target mux")
        branches.append((branch.group("guard").strip(), branch.group("value")))
        cursor = branch.end()
    default = body[cursor:].strip()
    if len(branches) != 6 or default != "'x":
        raise ValueError(
            f"expected six guarded branches and default 'x, got {len(branches)} / {default!r}"
        )
    rendered = [
        "always_comb begin",
        f"  {TARGET} = 'x;",
        "  (* parallel_case *) case (1'b1)",
    ]
    rendered.extend(f"    ({guard}): {TARGET} = {value};" for guard, value in branches)
    rendered.extend(["  endcase", "end"])
    replacement = "\n".join(rendered)
    return source[: match.start()] + replacement + source[match.end() :], len(branches)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    transformed, branch_count = _rewrite(raw.decode("utf-8"))
    output = transformed.encode("utf-8")
    args.output.write_bytes(output)
    args.receipt.write_text(
        json.dumps(
            {
                "schema": "llm2fpga.calyx-memory-write-mux-balance.v1",
                "status": "ok",
                "target": TARGET,
                "branches": branch_count,
                "input_sha256": _digest(raw),
                "output_sha256": _digest(output),
                "semantics": "parallel case over mutually-exclusive scheduled enables; default remains 'x",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
