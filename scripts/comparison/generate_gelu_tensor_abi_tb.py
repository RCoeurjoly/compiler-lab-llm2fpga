#!/usr/bin/env python3
"""Generate a packed GELU ABI testbench and the authoritative Q4.12 LUT."""
import argparse, json, math
from pathlib import Path

def u32(v): return int(v) & 0xffffffff

def lut_lines():
    out=[]
    for i in range(8192):
        x=-8.0+i/512.0
        y=0.5*x*(1.0+math.tanh(math.sqrt(2.0/math.pi)*(x+0.044715*x**3)))
        q=max(-32768,min(32767,round(y*4096.0)))
        out.append(f"{q & 0xffff:04x}")
    return '\n'.join(out)+'\n'

def generate(d):
    ins=d['oracle']['checkpoints']['block.mlp.fc_in']['values']
    exp=d['oracle']['checkpoints']['block.mlp.activation']['values']
    out=['`timescale 1ns/1ps','module tb_gelu_tensor;',
         'reg clk=0,rst=1,start=0; reg [8191:0] inputs_q16=0;',
         'wire done,busy; wire [8191:0] outputs_q16;',
         'llm2fpga_gelu_q16_tensor #(.D(256),.LUT_FILE("/tmp/gptneo_gelu.mem")) dut(.clk(clk),.rst(rst),.start(start),.inputs_q16(inputs_q16),.done(done),.busy(busy),.outputs_q16(outputs_q16));',
         'always #5 clk=~clk; initial begin repeat(2) @(posedge clk); rst<=0;']
    for i,v in enumerate(ins): out.append(f'inputs_q16[{i*32} +: 32] <= {u32(v)};')
    out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
    for i,v in enumerate(exp): out.append(f'if (outputs_q16[{i*32} +: 32] !== {u32(v)}) begin $display("lane {i} mismatch"); $fatal; end')
    out += ['$display("LLM2FPGA_GELU_TENSOR_PASS"); $finish; end endmodule','']
    return '\n'.join(out)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reference',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--lut',type=Path,required=True); a=ap.parse_args()
    d=json.loads(a.reference.read_text()); a.output.write_text(generate(d)); a.lut.write_text(lut_lines())
if __name__=='__main__': main()
