#!/usr/bin/env python3
"""Lower the packed authenticated softmax boundary to a Calyx primitive.

This deliberately targets the packed ``i16384`` ABI.  Calyx cannot lower a
tensor-valued ``func.call`` result, while a packed integer port is representable
by an external primitive and can therefore survive export to Futil.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


FUNC_RE = re.compile(r"func\.func\s+@([\w.$-]+)\(%scores:\s*i16384,\s*%position:\s*i32\)\s*->\s*i16384")


def lower(source: str) -> str:
    match = FUNC_RE.search(source)
    if not match:
        raise ValueError("expected packed softmax function ABI")
    name = match.group(1)
    # Keep the authenticated module attributes intact, but replace the
    # tensor/function boundary with the explicit Calyx external primitive.
    # The module attribute dictionary may itself contain braces; the module
    # body starts at the closing ``} {`` sequence on the first line.
    body_start = source.find("} {")
    if body_start < 0:
        raise ValueError("expected module attribute dictionary")
    prefix = source[: body_start + 3]
    # Calyx export requires an entrypoint component; retain the bridge
    # manifest while adding the explicit entrypoint marker.
    prefix = prefix.replace("module attributes {", "module attributes {calyx.entrypoint = \"" + name + "\", ", 1)
    return f'''{prefix}
  hw.module.extern @llm2fpga_attention_softmax_fixed_tensor(in %clk : i1 {{calyx.clk}}, in %rst : i1 {{calyx.reset}}, in %start : i1 {{calyx.go}}, in %position : i32, in %scores : i16384, out done : i1 {{calyx.done}}, out busy : i1, out probabilities : i16384) attributes {{filename = "llm2fpga_attention_softmax_fixed_tensor.sv"}}
  calyx.component @{name}(%scores: i16384, %position: i32, %go: i1 {{go}}, %clk: i1 {{clk}}, %reset: i1 {{reset}}) -> (%result: i16384, %done: i1 {{done}}) {{
    %one = hw.constant 1 : i1
    %prim.clk, %prim.rst, %prim.start, %prim.position, %prim.scores, %prim.done, %prim.busy, %prim.probabilities = calyx.primitive @prim of @llm2fpga_attention_softmax_fixed_tensor : i1, i1, i1, i32, i16384, i1, i1, i16384
    calyx.wires {{
      calyx.assign %prim.clk = %clk : i1
      calyx.assign %prim.rst = %reset : i1
      calyx.assign %prim.start = %go : i1
      calyx.assign %prim.position = %position : i32
      calyx.assign %prim.scores = %scores : i16384
      calyx.assign %result = %prim.probabilities : i16384
      calyx.assign %done = %prim.done : i1
    }}
    calyx.control {{}}
  }} {{toplevel}}
}}
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(lower(args.input.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
