#!/usr/bin/env python3
"""Share hierarchical predicates for every generated Calyx FSM comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


STATE_RE = re.compile(r"fsm0_out\s*==\s*11'd(\d+)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    source = raw.decode("utf-8")
    states = sorted({int(m.group(1)) for m in STATE_RE.finditer(source)})
    if not states:
        raise SystemExit("no generated fsm0_out state comparisons found")
    groups = sorted({state >> 5 for state in states})
    transformed = STATE_RE.sub(
        lambda m: (
            f"\n(fsm_hi_{int(m.group(1)) >> 5} && "
            f"fsm0_out[4:0] == 5'd{int(m.group(1)) & 31})"
        ),
        source,
    )
    declaration = "logic [10:0] fsm0_out;"
    if transformed.count(declaration) != 1:
        raise SystemExit("expected exactly one generated fsm0_out declaration")
    wires = "\n".join(
        f"wire fsm_hi_{group} = fsm0_out[10:5] == 6'd{group};" for group in groups
    )
    insert = transformed.index(declaration) + len(declaration)
    transformed = transformed[:insert] + "\n" + wires + transformed[insert:]
    output = transformed.encode("utf-8")
    args.output.write_bytes(output)
    args.receipt.write_text(
        json.dumps(
            {
                "schema": "llm2fpga.calyx-state-decode-partition.v1",
                "status": "ok",
                "states": len(states),
                "groups": groups,
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "output_sha256": hashlib.sha256(output).hexdigest(),
                "replacement": "fsm0_out == state -> shared upper-state predicate and lower-state comparison",
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
