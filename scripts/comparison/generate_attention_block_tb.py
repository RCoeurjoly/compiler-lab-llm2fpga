#!/usr/bin/env python3
import argparse,json
from pathlib import Path
def u(v,b): return int(v)&((1<<b)-1)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();d=json.loads(a.input.read_text());rows=d['softmax_rows'];
 out=['`timescale 1ns/1ps','module tb_attn_block; reg clk=0,rst=1,start=0; reg [2047:0] query_q16=0; reg [65535:0] keys_q16=0,values_q16=0; wire done,busy; wire [2047:0] context_q16;','llm2fpga_attention_block_tensor #(.EXP_FILE("/tmp/kev-attn/gptneo_exp.mem")) dut(.clk(clk),.rst(rst),.start(start),.position(5\'d3),.query_q16(query_q16),.keys_q16(keys_q16),.values_q16(values_q16),.done(done),.busy(busy),.context_q16(context_q16)); always #5 clk=~clk; initial begin repeat(2) @(posedge clk); rst<=0;']
 for h,row in enumerate(rows):
  for j,v in enumerate(row['query_q16_16']): out.append(f'query_q16[{(h*4+j)*32} +: 32] <= {u(v,32)};')
  for k,vec in enumerate(row['key_rows_q16_16']):
   for j,v in enumerate(vec): out.append(f'keys_q16[{((h*32+k)*4+j)*32} +: 32] <= {u(v,32)};')
  for k,vec in enumerate(row['value_rows_q16_16']):
   for j,v in enumerate(vec): out.append(f'values_q16[{((h*32+k)*4+j)*32} +: 32] <= {u(v,32)};')
 out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
 for h,row in enumerate(rows):
  for j,v in enumerate(row['context_q16_16']): out.append(f'if(context_q16[{(h*4+j)*32} +: 32] !== {u(v,32)}) begin $display("mismatch h{h} d{j}"); $fatal; end')
 out += ['$display("LLM2FPGA_ATTENTION_BLOCK_PASS"); $finish; end endmodule',''];a.output.write_text('\n'.join(out))
if __name__=='__main__':main()
