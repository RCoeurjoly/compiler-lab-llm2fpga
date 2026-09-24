#!/usr/bin/env python3
"""Run the one-port generated-RC external-memory transaction probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time


TB = r'''`timescale 1ns/1ps
module tb;
  logic clk = 1'b0;
  always #1 clk = ~clk;
  logic reset = 1'b1;
  logic go = 1'b0;
  logic done;
  logic ext_req_valid;
  logic ext_req_ready = 1'b1;
  logic [31:0] ext_req_addr;
  logic ext_rsp_valid = 1'b0;
  logic [63:0] ext_rsp_data = 64'd0;
  logic [7:0] result0, result1;
  logic [7:0] extmem [0:15];
  logic pending = 1'b0;
  logic [31:0] pending_addr = 32'd0;
  integer delay = 0;

  tinystories_integer_rc_external_probe_top dut (
    .clk(clk), .reset(reset), .go(go), .done(done),
    .ext_req_valid(ext_req_valid), .ext_req_ready(ext_req_ready),
    .ext_req_addr(ext_req_addr), .ext_rsp_valid(ext_rsp_valid),
    .ext_rsp_data(ext_rsp_data), .result0(result0), .result1(result1)
  );

  always @(posedge clk) begin
    ext_rsp_valid <= 1'b0;
    if (ext_req_valid && ext_req_ready) begin
      pending <= 1'b1;
      pending_addr <= ext_req_addr;
      delay <= 2;
    end
    if (pending) begin
      if (delay != 0)
        delay <= delay - 1;
      else begin
        ext_rsp_valid <= 1'b1;
        ext_rsp_data <= {56'd0, extmem[pending_addr[3:0]]};
        pending <= 1'b0;
      end
    end
  end

  initial begin
    $readmemh("external_mem0.hex", extmem);
    repeat (4) @(posedge clk);
    reset <= 1'b0;
    repeat (2) @(posedge clk);
    go <= 1'b1; // generated Calyx contract requires go to remain asserted
    wait (done);
    #1;
    if ({result1, result0} !== 16'h4cfe) begin
      $display("RC_EXTERNAL_PROBE_FAIL result=%04h", {result1, result0});
      $fatal(1);
    end
    $display("RC_EXTERNAL_PROBE_PASS result=%04h", {result1, result0});
    $finish;
  end
endmodule
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wrapper-dir", type=Path, required=True)
    parser.add_argument("--sv", type=Path, required=True)
    parser.add_argument("--generated-sv", type=Path, required=True)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    tb = args.wrapper_dir / "tb.sv"
    tb.write_text(TB, encoding="utf-8")
    obj = args.wrapper_dir / "obj_dir"
    compile_log = args.wrapper_dir / "verilator-build.log"
    with compile_log.open("w", encoding="utf-8") as log:
        started = time.monotonic()
        result = subprocess.run([
            args.verilator, "--binary", "--top-module", "tb", "--Mdir", str(obj),
            "-Wno-fatal", "-Wno-WIDTHEXPAND", "-Wno-WIDTHTRUNC", "-j", str(args.jobs),
            str(args.sv), str(args.generated_sv), str(tb),
        ], stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(f"Verilator compile failed; see {compile_log}")
    simulation_log = args.wrapper_dir / "simulation.log"
    with simulation_log.open("w", encoding="utf-8") as log:
        result = subprocess.run([str(obj / "Vtb")], cwd=args.wrapper_dir,
                                stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit(f"simulation failed; see {simulation_log}")
    text = simulation_log.read_text(encoding="utf-8")
    if "RC_EXTERNAL_PROBE_PASS" not in text:
        raise SystemExit("simulation did not report RC_EXTERNAL_PROBE_PASS")
    print(json.dumps({"schema": "tinystories-integer-rc-external-probe-run-v1",
                      "status": "pass", "simulation_log": str(simulation_log)}, sort_keys=True))


if __name__ == "__main__":
    main()
