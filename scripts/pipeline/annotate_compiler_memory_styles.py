#!/usr/bin/env python3
"""Selectively annotate compiler memories for Xilinx BRAM legalization.

The generated RC contains many tiny ``seq_mem_d1`` instances.  Forcing every
instance to BRAM is invalid (for example an 8x1 memory has no legal Xilinx
BRAM mapping), while leaving all choices unconstrained makes MEMORY_LIBMAP
explore a large set of equivalent candidates.  This pass only annotates
conservative, sufficiently deep shapes and leaves the rest to Yosys.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


INSTANCE = re.compile(
    r"(?ms)(?P<prefix>\bseq_mem_d1\s*#\s*\(\s*"
    r"\.IDX_SIZE\((?P<idx>\d+)\),\s*\.SIZE\((?P<size>\d+)\),\s*"
    r"\.WIDTH\((?P<width>\d+)\)\s*\)\s*)"
    r"(?P<name>mem_\d+)\s*\("
)

# Widths that correspond to native or straightforwardly packed 7-series BRAM
# modes.  The depth/bit threshold below prevents tiny memories from being
# forced into a block (the rejected global experiment failed on 8x1).
BRAM_WIDTHS = {8, 9, 16, 18, 32, 36, 64, 72}
MIN_DEPTH = 8
MIN_BITS = 256


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def annotate(source: str) -> tuple[str, dict[str, object]]:
    counts = {"instances": 0, "bram_annotations": 0, "left_unconstrained": 0}
    shapes: dict[str, int] = {}

    def replace(match: re.Match[str]) -> str:
        counts["instances"] += 1
        size = int(match.group("size"))
        width = int(match.group("width"))
        shape = f"{width}x{size}"
        shapes[shape] = shapes.get(shape, 0) + 1
        eligible = (
            width in BRAM_WIDTHS and size >= MIN_DEPTH and width * size >= MIN_BITS
        )
        if not eligible:
            counts["left_unconstrained"] += 1
            return match.group(0)
        counts["bram_annotations"] += 1
        return f'(* ram_style = "block" *) {match.group(0)}'

    output = INSTANCE.sub(replace, source)
    receipt = {
        "schema": "llm2fpga.compiler-memory-style.v1",
        "input_sv_sha256": _sha256(source),
        "output_sv_sha256": _sha256(output),
        "policy": {
            "bram_widths": sorted(BRAM_WIDTHS),
            "minimum_depth": MIN_DEPTH,
            "minimum_bits": MIN_BITS,
        },
        "counts": counts,
        "shapes": dict(sorted(shapes.items())),
    }
    return output, receipt


def main() -> int:
    if len(sys.argv) != 4:
        print(
            f"usage: {sys.argv[0]} <input.sv> <output.sv> <receipt.json>",
            file=sys.stderr,
        )
        return 2
    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    output, receipt = annotate(source)
    Path(sys.argv[2]).write_text(output, encoding="utf-8")
    Path(sys.argv[3]).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
