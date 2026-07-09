#!/usr/bin/env python3
"""Generate SV for Calyx compile.futil primitives used by native Verilog."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_MARKERS = {
    "undef": "primitive undef",
    "std_wire": "comb primitive std_wire",
    "std_add": "comb primitive std_add",
    "std_reg": "primitive std_reg",
}


COMPILE_PRIMITIVES_SV = """`default_nettype none
module undef #(parameter WIDTH = 32) (
  output logic [WIDTH-1:0] out
);
  assign out = 'x;
endmodule

module std_wire #(parameter WIDTH = 32) (
  input wire logic [WIDTH-1:0] in,
  output logic [WIDTH-1:0] out
);
  assign out = in;
endmodule

module std_add #(parameter WIDTH = 32) (
  input wire logic [WIDTH-1:0] left,
  input wire logic [WIDTH-1:0] right,
  output logic [WIDTH-1:0] out
);
  assign out = left + right;
endmodule

module std_reg #(parameter WIDTH = 32) (
  input wire logic [WIDTH-1:0] in,
  input wire logic write_en,
  input wire logic clk,
  input wire logic reset,
  output logic [WIDTH-1:0] out,
  output logic done
);
  always_ff @(posedge clk) begin
    if (reset) begin
      out <= 0;
      done <= 0;
    end else if (write_en) begin
      out <= in;
      done <= 1'd1;
    end else begin
      done <= 1'd0;
    end
  end
endmodule
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-futil", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    compile_futil = Path(args.compile_futil)
    output = Path(args.output)
    text = compile_futil.read_text(encoding="utf-8")

    missing = [
        f"{name} ({marker})"
        for name, marker in REQUIRED_MARKERS.items()
        if marker not in text
    ]
    if missing:
        raise SystemExit(
            "compile.futil does not contain expected Calyx primitives: "
            + ", ".join(missing)
        )

    output.write_text(COMPILE_PRIMITIVES_SV, encoding="utf-8")


if __name__ == "__main__":
    main()
