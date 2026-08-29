#!/usr/bin/env python3
"""Generate a deterministic packed tensor-ABI softmax testbench."""
import argparse, json
from pathlib import Path

def generate(ref):
    rows = ref["softmax_rows"]
    out = [
        '`timescale 1ns/1ps',
        'module tb_tensor_abi;',
        'reg clk=0,rst=1,start=0; reg [31:0] position=3;',
        'reg [16383:0] scores=0; wire done,busy; wire [16383:0] probabilities; integer fail=0;',
        'llm2fpga_attention_softmax_fixed_tensor #(.EXP_FILE("/tmp/kev-attn/gptneo_exp.mem")) dut(.*);',
        'always #5 clk=~clk;',
        'initial begin repeat(2) @(posedge clk); rst<=0;'
    ]
    for h, row in enumerate(rows):
        for k, value in enumerate(row["score_codes_q8_8"]):
            out.append(f'scores[{(h*32+k)*32} +: 32] <= {value};')
    out += ['@(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
    for h, row in enumerate(rows):
        for k, value in enumerate(row["probabilities_q1_20"]):
            off = (h*32+k)*32
            out.append(f'if (probabilities[{off} +: 21] !== {value}) begin $display("head {h} key {k} mismatch"); fail=fail+1; end')
            out.append(f'if (probabilities[{off+21} +: 11] !== 0) begin $display("head {h} key {k} upper bits nonzero"); fail=fail+1; end')
    out += ['if(fail==0) $display("GPTNEO_SOFTMAX_TENSOR_ABI_16_ROWS_PASS"); else $fatal(1); $finish; end endmodule', '']
    return '\n'.join(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--reference', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(); args.output.write_text(generate(json.loads(args.reference.read_text())))

if __name__ == '__main__':
    main()
