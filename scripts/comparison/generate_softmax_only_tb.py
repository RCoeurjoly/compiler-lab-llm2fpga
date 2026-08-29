#!/usr/bin/env python3
"""Generate an Icarus testbench from the authenticated fixed-softmax rows."""
import argparse, json
from pathlib import Path

def generate(reference: dict) -> str:
    rows = reference["softmax_rows"]
    lines = ["`timescale 1ns/1ps", "module tb_generated;", "reg clk=0,rst=1,start=0,in_valid=0,out_ready=1; reg [4:0] position; reg signed [31:0] in_score; wire in_ready,out_valid,busy; wire [4:0] out_index; wire [20:0] out_probability; integer r,n,failures=0;", "gptneo_softmax_only #(.TMAX(32),.EXP_FILE(\"/tmp/kev-attn/gptneo_exp.mem\")) dut(.*);", "always #5 clk=~clk;", "initial begin repeat(2) @(posedge clk); rst<=0;"]
    for r, row in enumerate(rows):
        scores = row["score_codes_q8_8"]; expected = row["probabilities_q1_20"]
        lines += [f"position<=3; @(posedge clk); start<=1; @(posedge clk); start<=0;"]
        for n, score in enumerate(scores):
            lines += [f"@(posedge clk); in_valid<=1; in_score<={score};"]
        lines += ["@(posedge clk); in_valid<=0; wait(out_valid);"]
        for n, value in enumerate(expected):
            lines += [f"@(posedge clk); if(out_probability !== {value}) begin $display(\"row {r} index {n}: %0d != {value}\",out_probability); failures=failures+1; end"]
    lines += ["if(failures==0) $display(\"GPTNEO_SOFTMAX_ONLY_16_ROWS_PASS\"); else $fatal(1); $finish; end endmodule", ""]
    return "\n".join(lines)

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--reference",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    a.output.write_text(generate(json.loads(a.reference.read_text())), encoding="utf-8")
if __name__ == "__main__": main()
