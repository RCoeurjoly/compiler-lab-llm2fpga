#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
import numpy as np

def u(v,bits): return int(v) & ((1<<bits)-1)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--package',type=Path,required=True); ap.add_argument('--checkpoints',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    sys.path.insert(0,'/home/roland/kev-gpt/.worktrees/kintex-selftest')
    from tinystories.int_reference import IntegerGPTNeo
    p=IntegerGPTNeo(a.package); c=json.loads(a.checkpoints.read_text())['attention_context_q16_16']['values'];
    w=p.tensor_codes['blocks.0.attn.out.weight']; ws=np.rint(p.tensor_scales['blocks.0.attn.out.weight']*(1<<24)).astype(np.int64)
    bias=np.rint(p.tensors['blocks.0.attn.out.bias']*(1<<16)).astype(np.int64)
    ins=np.rint(p.activation_scales['transformer.h.0.attn.attention.out_proj.input']*(1<<24)).astype(np.int64)
    outs=np.rint(p.activation_scales['transformer.h.0.attn.attention.out_proj.output']*(1<<24)).astype(np.int64)
    # Use the authenticated package runtime for the expected checkpoint; the
    # RTL receives the same packed codes/scales and must reproduce its Q16.
    ic=np.clip(np.rint(np.asarray(c,dtype=np.float64)/ (ins/(1<<24))),-128,127).astype(np.int64)
    exp=np.asarray(json.loads(a.checkpoints.read_text())['attention_output_q16_16']['values'],dtype=np.int64)
    out=['`timescale 1ns/1ps','module tb_attn_out; reg clk=0,rst=1,start=0; reg [2047:0] activations_q16=0; reg [1535:0] input_scales_q24=0; reg [1535:0] weight_scales_q24=0,output_scales_q24=0; reg [32767:0] weights_q8=0; reg [2047:0] bias_q16=0; wire done,busy; wire [2047:0] outputs_q16;','llm2fpga_gemv_w8a8_tensor #(.M(64),.K(64)) dut(.*); always #5 clk=~clk; initial begin repeat(2) @(posedge clk); rst<=0;']
    for i,v in enumerate(c): out.append(f'activations_q16[{i*32} +: 32] <= {u(v,32)};')
    for i,v in enumerate(ins): out.append(f'input_scales_q24[{i*24} +: 24] <= {u(v,24)};')
    for i,v in enumerate(ws): out.append(f'weight_scales_q24[{i*24} +: 24] <= {u(v,24)};')
    for i,v in enumerate(outs): out.append(f'output_scales_q24[{i*24} +: 24] <= {u(v,24)};')
    for i,v in enumerate(w.reshape(-1)): out.append(f'weights_q8[{i*8} +: 8] <= {u(v,8)};')
    for i,v in enumerate(bias): out.append(f'bias_q16[{i*32} +: 32] <= {u(v,32)};')
    out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
    for i,v in enumerate(exp): out.append(f'if (outputs_q16[{i*32} +: 32] !== {u(v,32)}) begin $display("lane {i} mismatch exp={u(v,32)} got=%h",outputs_q16[{i*32} +: 32]); $fatal; end')
    out += ['$display("LLM2FPGA_GEMV_ATTN_OUT_PASS"); $finish; end endmodule','']; a.output.write_text('\n'.join(out))
if __name__=='__main__': main()
