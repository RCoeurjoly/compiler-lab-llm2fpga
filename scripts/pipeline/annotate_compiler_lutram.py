#!/usr/bin/env python3
"""Add the Xilinx distributed-RAM hint to generated LUTRAM memories.

The compiler-generated ``seq_mem_d1_lutram`` primitive already contains a
registered read address and read-data stage.  This pass only adds a synthesis
attribute so Yosys cannot remap that primitive to asynchronous BRAM outputs.
It deliberately refuses to edit any other memory primitive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MODULE = "module seq_mem_d1_lutram #"
NEEDLE = "  logic [WIDTH-1:0] mem[SIZE-1:0];"
ATTRIBUTE = '  (* ram_style = "distributed" *)\n'


def annotate(source: str) -> tuple[str, bool]:
    start = source.find(MODULE)
    if start < 0:
        raise ValueError("generated source has no seq_mem_d1_lutram primitive")
    end = source.find("endmodule", start)
    if end < 0:
        raise ValueError("unterminated seq_mem_d1_lutram primitive")
    body = source[start:end]
    if ATTRIBUTE in body:
        return source, False
    if body.count(NEEDLE) != 1:
        raise ValueError("expected exactly one LUTRAM memory declaration")
    body = body.replace(NEEDLE, ATTRIBUTE + NEEDLE, 1)
    return source[:start] + body + source[end:], True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    original = args.source.read_text()
    annotated, changed = annotate(original)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(annotated)
    receipt = {
        "schema": "tinystories-compiler-lutram-annotation-v1",
        "status": "passed",
        "changed": changed,
        "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "destination_sha256": hashlib.sha256(annotated.encode()).hexdigest(),
        "semantic_claim": "synthesis attribute only; no RTL statements or interfaces changed",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
