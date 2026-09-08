#!/usr/bin/env python3
"""Adapt Yosys XC7 BRAM techmap parameters to memory_libmap's cell ABI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


REPLACEMENTS = (
    ("PORT_A_RD_WIDTH", "PORT_A_WIDTH"),
    ("PORT_B_RD_WIDTH", "PORT_B_WIDTH"),
    ("PORT_A_RD_USED", "PORT_A_USED"),
    ("PORT_B_RD_USED", "PORT_B_USED"),
)


def transform(source: str) -> tuple[str, dict[str, object]]:
    output = source
    counts: dict[str, int] = {}
    for old, new in REPLACEMENTS:
        output, count = output.replace(old, new), output.count(old)
        counts[old] = count
    return output, {
        "schema": "llm2fpga.xc7-bram-compat-map.v1",
        "input_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "replacement_count": sum(counts.values()),
        "replacements": counts,
    }


def main() -> int:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <input-map.v> <output-map.v> <receipt.json>", file=sys.stderr)
        return 2
    source = Path(sys.argv[1]).read_text()
    output, receipt = transform(source)
    Path(sys.argv[2]).write_text(output)
    Path(sys.argv[3]).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
