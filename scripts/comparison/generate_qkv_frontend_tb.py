#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
import numpy as np
def u(v,b): return int(v)&((1<<b)-1)
def emit(o,n,v,b):
 for i,x in enumerate(np.asarray(v).reshape(-1)): o.append(f'{n}[{i*b} +: {b}] <= {u(x,b)};')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--oracle',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,'/home/roland/kev-gpt/.worktrees/kintex-selftest');from tinystories.int_reference import IntegerGPTNeo
 p=IntegerGPTNeo(a.package);o=json.loads(a.oracle.read_text())['oracle']['checkpoints'];
 def sc(k): return np.rint(p.activation_scales[k]*(1<<24)).astype(np.int64)
 out=['`timescale 1ns/1ps','module tb_qkv; reg clk=0,rst=1,start=0; reg [2047:0] input_q16=0,gamma_q16=0,beta_q16=0; reg [1535:0] q_in_scales=0,q_out_scales=0,k_in_scales=0,k_out_scales=0,v_in_scales=0,v_out_scales=0,q_weight_scales=0,k_weight_scales=0,v_weight_scales=0; reg [32767:0] q_weights=0,k_weights=0,v_weights=0; reg [2047:0] q_bias=0,k_bias=0,v_bias=0; wire done,busy; wire [2047:0] q_out,k_out,v_out;','llm2fpga_qkv_frontend_tensor dut(.*); always #5 clk=~clk; initial begin repeat(2) @(posedge clk); rst<=0;']
 emit(out,'input_q16',o['block.input']['values'],32);emit(out,'gamma_q16',np.rint(p.tensors['blocks.0.ln1.weight']*(1<<16)),32);emit(out,'beta_q16',np.rint(p.tensors['blocks.0.ln1.bias']*(1<<16)),32)
 for n,key in [('q','q_proj'),('k','k_proj'),('v','v_proj')]:
  emit(out,n+'_in_scales',sc(f'transformer.h.0.attn.attention.{key}.input'),24);emit(out,n+'_out_scales',sc(f'transformer.h.0.attn.attention.{key}.output'),24);emit(out,n+'_weights',p.tensor_codes[f'blocks.0.attn.{n}.weight'].reshape(-1),8);emit(out,n+'_weight_scales',np.rint(p.tensor_scales[f'blocks.0.attn.{n}.weight']*(1<<24)),24);emit(out,n+'_bias',np.zeros(64,dtype=np.int64),32)
 out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
 for n,ck in [('q','block.attention.q'),('k','block.attention.k'),('v','block.attention.v')]:
  for i,x in enumerate(np.asarray(o[ck]['values']).reshape(-1)): out.append(f'if({n}_out[{i*32} +: 32] !== {u(x,32)}) begin $display("{n} lane {i} mismatch"); $fatal; end')
 out += ['$display("LLM2FPGA_QKV_FRONTEND_PASS"); $finish; end endmodule',''];a.output.write_text('\n'.join(out))
if __name__=='__main__':main()
