#!/usr/bin/env python3
"""Remove redundant operand widening in Calyx's signed fixed-point multiply.

Calyx emits a WIDTH-bit multiply helper whose signed branch sign-extends both
operands to 2*WIDTH before multiplying.  The helper already stores a 2*WIDTH
result and extracts the fixed-point slice afterwards; widening the operands
turns a 64x64 operation into a 128x128 operation.  This repair keeps the
2*WIDTH result context while leaving the operand widths at WIDTH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


OLD = """out_tmp <= $signed(
          { {WIDTH{ltmp[WIDTH-1]}}, ltmp} *
          { {WIDTH{rtmp[WIDTH-1]}}, rtmp}
        );"""
NEW = "out_tmp <= $signed(ltmp) * $signed(rtmp);"


def repair(source: Path, destination: Path, receipt: Path) -> None:
    text = source.read_text(encoding="utf-8")
    matches = text.count(OLD)
    if matches != 1:
        raise ValueError(f"expected exactly one signed multiply helper, found {matches}")
    repaired = text.replace(OLD, NEW)
    destination.write_text(repaired, encoding="utf-8")
    receipt.write_text(
        json.dumps(
            {
                "schema": "llm2fpga-calyx-signed-multiply-width-repair-v1",
                "status": "ok",
                "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "repaired_sha256": hashlib.sha256(repaired.encode()).hexdigest(),
                "replacements": matches,
                "operand_width_policy": "WIDTH operands, 2*WIDTH result context",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    repair(args.source, args.destination, args.receipt)


if __name__ == "__main__":
    main()
