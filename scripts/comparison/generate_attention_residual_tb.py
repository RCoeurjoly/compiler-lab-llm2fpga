#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
import numpy as np
def u(v,b): return int(v)&((1<<b)-1)
def emit(o,n,v,b):
 for i,x in enumerate(np.asarray(v).reshape(-1)): o.append(f'{n}[{i*b} +: {b}] <= {u(x,b)};')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,'/home/roland/kev-gpt/.worktrees/kintex-selftest');from tinystories.int_reference import IntegerGPTNeo
 p=IntegerGPTNeo(a.package);d=json.loads(a.input.read_text());rows=d['softmax_rows'];o=d['attention_output_q16_16']['values']; oracle=json.loads(Path('artifacts/reference/tinystories-1m-candidate-oracle.json').read_text())['oracle']['checkpoints'];res=oracle['block.residual.attention']['values']
 def sc(k): return np.rint(p.activation_scales[k]*(1<<24)).astype(np.int64)
 wi=p.tensor_codes['blocks.0.attn.out.weight'];ws=np.rint(p.tensor_scales['blocks.0.attn.out.weight']*(1<<24)).astype(np.int64);bi=np.rint(p.tensors['blocks.0.attn.out.bias']*(1<<16)).astype(np.int64);ins=sc('transformer.h.0.attn.attention.out_proj.input');outs=sc('transformer.h.0.attn.attention.out_proj.output')
 out=['`timescale 1ns/1ps','module tb_attn_res; reg clk=0,rst=1,start=0; reg [4:0] position=3; reg [2047:0] query_q16=0,block_input_q16=0; reg [65535:0] keys_q16=0,values_q16=0; reg [1535:0] input_scales_q24=0,weight_scales_q24=0,output_scales_q24=0; reg [32767:0] weights_q8=0; reg [2047:0] bias_q16=0; wire done,busy; wire [2047:0] residual_q16;','llm2fpga_attention_residual_tensor #(.EXP_FILE("/tmp/kev-attn/gptneo_exp.mem")) dut(.*); always #5 clk=~clk; initial begin repeat(2) @(posedge clk); rst<=0;']
 for h,r in enumerate(rows):
  for j,x in enumerate(r['query_q16_16']): out.append(f'query_q16[{(h*4+j)*32} +: 32] <= {u(x,32)};')
  for k,v in enumerate(r['key_rows_q16_16']):
   for j,x in enumerate(v): out.append(f'keys_q16[{((h*32+k)*4+j)*32} +: 32] <= {u(x,32)};')
  for k,v in enumerate(r['value_rows_q16_16']):
   for j,x in enumerate(v): out.append(f'values_q16[{((h*32+k)*4+j)*32} +: 32] <= {u(x,32)};')
 emit(out,'block_input_q16',oracle['block.input']['values'],32);emit(out,'input_scales_q24',ins,24);emit(out,'weights_q8',wi.reshape(-1),8);emit(out,'weight_scales_q24',ws,24);emit(out,'bias_q16',bi,32);emit(out,'output_scales_q24',outs,24)
 out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
 for i,v in enumerate(res): out.append(f'if(residual_q16[{i*32} +: 32] !== {u(v,32)}) begin $display("lane {i} mismatch exp={u(v,32)} got=%h proj=%h ctx=%h",residual_q16[{i*32} +: 32],dut.projected[{i*32} +: 32],dut.attn_context[{i*32} +: 32]); $fatal; end')
 out += ['$display("LLM2FPGA_ATTENTION_RESIDUAL_PASS"); $finish; end endmodule',''];a.output.write_text('\n'.join(out))
if __name__=='__main__':main()
