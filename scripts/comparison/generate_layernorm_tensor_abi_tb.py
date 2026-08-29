#!/usr/bin/env python3
"""Generate a packed 64-lane LayerNorm ABI testbench."""
import argparse, json
from pathlib import Path

def u32(value): return int(value) & 0xffffffff

def generate(vector):
    out = ['`timescale 1ns/1ps', 'module tb_ln_tensor;',
           'reg clk=0,rst=1,start=0; reg [2047:0] input_values=0,gamma_values=0,beta_values=0;',
           'wire done,busy; wire [2047:0] output_values;',
           'llm2fpga_fixed_layer_norm_q16_16_tensor dut(.*); always #5 clk=~clk;',
           'initial begin repeat(2) @(posedge clk); rst<=0;']
    for name in ('input_q16_16', 'gamma_q16_16', 'beta_q16_16'):
        base = name.split('_')[0]
        for i, value in enumerate(vector[name]):
            out.append(f'{base}_values[{i*32} +: 32] <= {u32(value)};')
    out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
    for i, value in enumerate(vector['result']['output_q16_16']):
        out.append(f'if (output_values[{i*32} +: 32] !== {u32(value)}) begin $display("lane {i} mismatch"); $fatal; end')
    out += ['$display("GPTNEO_LAYERNORM_TENSOR_ABI_PASS"); $finish; end endmodule', '']
    return '\n'.join(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--reference', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(); args.output.write_text(generate(json.loads(args.reference.read_text())))

if __name__ == '__main__': main()
