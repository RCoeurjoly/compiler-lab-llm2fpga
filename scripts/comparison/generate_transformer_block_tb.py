#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
import numpy as np
def u(v,b):return int(v)&((1<<b)-1)
def emit(o,n,v,b):
 for i,x in enumerate(np.asarray(v).reshape(-1)):o.append(f'{n}[{i*b} +: {b}] <= {u(x,b)};')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--oracle',type=Path,required=True);ap.add_argument('--softmax',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,'/home/roland/kev-gpt/.worktrees/kintex-selftest');from tinystories.int_reference import IntegerGPTNeo
 p=IntegerGPTNeo(a.package);o=json.loads(a.oracle.read_text())['oracle']['checkpoints'];s=json.loads(a.softmax.read_text());rows=s['softmax_rows']
 def sc(k):return np.rint(p.activation_scales[k]*(1<<24)).astype(np.int64)
 out=['`timescale 1ns/1ps','module tb_transformer; reg clk=0,rst=1,start=0; reg [4:0] position=3; reg [2047:0] input_q16=0,ln1_gamma=0,ln1_beta=0,ln2_gamma=0,ln2_beta=0; reg [65535:0] keys_q16=0,values_q16=0; reg [1535:0] q_in_scales=0,q_out_scales=0,k_in_scales=0,k_out_scales=0,v_in_scales=0,v_out_scales=0; reg [32767:0] q_weights=0,k_weights=0,v_weights=0; reg [1535:0] q_weight_scales=0,k_weight_scales=0,v_weight_scales=0; reg [2047:0] q_bias=0,k_bias=0,v_bias=0; reg [1535:0] attn_in_scales=0,attn_weight_scales=0,attn_out_scales=0; reg [32767:0] attn_weights=0; reg [2047:0] attn_bias=0; reg [1535:0] fc_in_input_scales=0; reg [131071:0] fc_in_weights=0; reg [6143:0] fc_in_weight_scales=0,fc_in_output_scales=0; reg [8191:0] fc_in_bias=0; reg [6143:0] fc_out_input_scales=0; reg [131071:0] fc_out_weights=0; reg [1535:0] fc_out_weight_scales=0,fc_out_output_scales=0; reg [2047:0] fc_out_bias=0; wire done,busy; wire [2047:0] output_q16; llm2fpga_transformer_block_tensor #(.EXP_FILE("/tmp/kev-attn/gptneo_exp.mem"),.GELU_FILE("/tmp/gptneo_gelu.mem")) dut(.*); always #5 clk=~clk; initial begin repeat(2) @(posedge clk); rst<=0;']
 emit(out,'input_q16',o['block.input']['values'],32);emit(out,'ln1_gamma',np.rint(p.tensors['blocks.0.ln1.weight']*(1<<16)),32);emit(out,'ln1_beta',np.rint(p.tensors['blocks.0.ln1.bias']*(1<<16)),32);emit(out,'ln2_gamma',np.rint(p.tensors['blocks.0.ln2.weight']*(1<<16)),32);emit(out,'ln2_beta',np.rint(p.tensors['blocks.0.ln2.bias']*(1<<16)),32)
 for h,r in enumerate(rows):
  for k,v in enumerate(r['key_rows_q16_16']):
   for j,x in enumerate(v):out.append(f'keys_q16[{((h*32+k)*4+j)*32} +: 32] <= {u(x,32)};')
  for k,v in enumerate(r['value_rows_q16_16']):
   for j,x in enumerate(v):out.append(f'values_q16[{((h*32+k)*4+j)*32} +: 32] <= {u(x,32)};')
  for j,x in enumerate(r['query_q16_16']):out.append(f'input_q16[{j*32} +: 32] <= {u(o["block.input"]["values"][j],32)};')
 for n,key in [('q','q_proj'),('k','k_proj'),('v','v_proj')]: emit(out,n+'_in_scales',sc(f'transformer.h.0.attn.attention.{key}.input'),24);emit(out,n+'_out_scales',sc(f'transformer.h.0.attn.attention.{key}.output'),24);emit(out,n+'_weights',p.tensor_codes[f'blocks.0.attn.{n}.weight'].reshape(-1),8);emit(out,n+'_weight_scales',np.rint(p.tensor_scales[f'blocks.0.attn.{n}.weight']*(1<<24)),24);emit(out,n+'_bias',np.zeros(64,dtype=np.int64),32)
 emit(out,'attn_in_scales',sc('transformer.h.0.attn.attention.out_proj.input'),24);emit(out,'attn_weights',p.tensor_codes['blocks.0.attn.out.weight'].reshape(-1),8);emit(out,'attn_weight_scales',np.rint(p.tensor_scales['blocks.0.attn.out.weight']*(1<<24)),24);emit(out,'attn_bias',np.rint(p.tensors['blocks.0.attn.out.bias']*(1<<16)),32);emit(out,'attn_out_scales',sc('transformer.h.0.attn.attention.out_proj.output'),24)
 # MLP arrays
 emit(out,'fc_in_input_scales',sc('transformer.h.0.mlp.c_fc.input'),24);emit(out,'fc_in_weights',p.tensor_codes['blocks.0.mlp.fc.weight'].reshape(-1),8);emit(out,'fc_in_weight_scales',np.rint(p.tensor_scales['blocks.0.mlp.fc.weight']*(1<<24)),24);emit(out,'fc_in_output_scales',sc('transformer.h.0.mlp.c_fc.output'),24);emit(out,'fc_in_bias',np.rint(p.tensors['blocks.0.mlp.fc.bias']*(1<<16)),32);emit(out,'fc_out_input_scales',sc('transformer.h.0.mlp.c_proj.input'),24);emit(out,'fc_out_weights',p.tensor_codes['blocks.0.mlp.proj.weight'].reshape(-1),8);emit(out,'fc_out_weight_scales',np.rint(p.tensor_scales['blocks.0.mlp.proj.weight']*(1<<24)),24);emit(out,'fc_out_output_scales',sc('transformer.h.0.mlp.c_proj.output'),24);emit(out,'fc_out_bias',np.rint(p.tensors['blocks.0.mlp.proj.bias']*(1<<16)),32)
 out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
 for i,x in enumerate(o['block.output']['values']): out.append(f'if(output_q16[{i*32} +: 32] !== {u(x,32)}) begin $display("lane {i} mismatch"); $fatal; end')
 out += ['$display("LLM2FPGA_TRANSFORMER_BLOCK_PASS"); $finish; end endmodule',''];a.output.write_text('\n'.join(out))
 # The generated pass marker is meaningful only after all output lanes compare.
 # (The launch/wait line above is retained for compatibility.)
if __name__=='__main__':main()
