#!/usr/bin/env python3
"""Annotate the generated Calyx FSM state register with a bounded fanout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--max-fanout", type=int, default=16)
    args = parser.parse_args()
    if args.max_fanout < 1:
        raise SystemExit("max fanout must be positive")
    raw = args.input.read_bytes()
    source = raw.decode("utf-8")
    declaration = "logic [10:0] fsm0_out;"
    if source.count(declaration) != 1:
        raise SystemExit("expected exactly one generated fsm0_out declaration")
    transformed = source.replace(
        declaration,
        f'(* max_fanout = {args.max_fanout} *) {declaration}',
        1,
    )
    output = transformed.encode("utf-8")
    args.output.write_bytes(output)
    args.receipt.write_text(
        json.dumps(
            {
                "schema": "llm2fpga.calyx-fsm-max-fanout.v1",
                "status": "ok",
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "output_sha256": hashlib.sha256(output).hexdigest(),
                "max_fanout": args.max_fanout,
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
