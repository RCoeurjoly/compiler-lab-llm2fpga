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

SCALAR_INSTANCE = re.compile(
    r"(?ms)(?P<prefix>\b)seq_mem_d1(?P<params>\s*#\s*\(\s*"
    r"\.IDX_SIZE\((?P<idx>\d+)\),\s*\.SIZE\(1\),\s*"
    r"\.WIDTH\((?P<width>\d+)\)\s*\)\s*)"
    r"(?P<name>mem_\d+)\s*\("
)

PAD_INSTANCE = re.compile(
    r"(?ms)\bseq_mem_d1\s*#\s*\(\s*"
    r"\.IDX_SIZE\((?P<idx>\d+)\),\s*\.SIZE\((?P<size>[2-9]|1\d|2\d)\),\s*"
    r"\.WIDTH\((?P<width>\d+)\)\s*\)\s*mem_\d+\s*\("
)

SCALAR_MODULE = r'''
module seq_mem_d1_scalar #(
    parameter WIDTH = 32,
    parameter SIZE = 1,
    parameter IDX_SIZE = 1
) (
   input wire logic clk,
   input wire logic reset,
   input wire logic [IDX_SIZE-1:0] addr0,
   input wire logic content_en,
   output logic done,
   output logic [WIDTH-1:0] read_data,
   input wire logic [WIDTH-1:0] write_data,
   input wire logic write_en
);
  logic [WIDTH-1:0] mem;
  logic [WIDTH-1:0] read_out;
  assign read_data = read_out;
  always_ff @(posedge clk) begin
    if (reset)
      read_out <= '0;
    else if (content_en && !write_en)
      read_out <= mem;
    else if (content_en && write_en)
      read_out <= 'x;
  end
  always_ff @(posedge clk) begin
    if (reset)
      done <= '0;
    else if (content_en)
      done <= '1;
    else
      done <= '0;
  end
  always_ff @(posedge clk) begin
    if (!reset && content_en && write_en)
      mem <= write_data;
  end
endmodule

'''

# Widths that correspond to native or straightforwardly packed 7-series BRAM
# modes.  The depth/bit threshold below prevents tiny memories from being
# forced into a block (the rejected global experiment failed on 8x1).
BRAM_WIDTHS = {8, 9, 16, 18, 32, 36, 64, 72}
MIN_DEPTH = 512
MIN_BITS = 4096
PAD_DEPTH = 32
PAD_IDX_SIZE = 5


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def annotate(source: str) -> tuple[str, dict[str, object]]:
    counts = {"instances": 0, "bram_annotations": 0, "left_unconstrained": 0}
    scalar_repairs = 0
    padded_repairs = 0
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

    def scalarize(match: re.Match[str]) -> str:
        nonlocal scalar_repairs
        scalar_repairs += 1
        return f"seq_mem_d1_scalar{match.group('params')}{match.group('name')} ("

    output, scalar_repairs = SCALAR_INSTANCE.subn(scalarize, output)
    if scalar_repairs:
        output = SCALAR_MODULE + output

    def pad(match: re.Match[str]) -> str:
        nonlocal padded_repairs
        padded_repairs += 1
        text = match.group(0)
        text = re.sub(r"\.IDX_SIZE\(\d+\)", f".IDX_SIZE({PAD_IDX_SIZE})", text, count=1)
        text = re.sub(r"\.SIZE\(\d+\)", f".SIZE({PAD_DEPTH})", text, count=1)
        return text

    output, padded_repairs = PAD_INSTANCE.subn(pad, output)
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
        "scalar_size1_repairs": scalar_repairs,
        "padded_shallow_repairs": padded_repairs,
        "padding": {"depth": PAD_DEPTH, "idx_size": PAD_IDX_SIZE},
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
