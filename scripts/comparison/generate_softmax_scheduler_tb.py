import argparse,json
from pathlib import Path
def generate(ref):
  rows=ref['softmax_rows']; lines=['`timescale 1ns/1ps','module tb_sched; reg clk=0,rst=1,start=0; reg [4:0] position=3; reg [16383:0] scores=0; wire done,busy; wire [10751:0] probabilities; integer fail=0,i;','llm2fpga_attention_softmax_scheduler #(.EXP_FILE("/tmp/kev-attn/gptneo_exp.mem")) dut(.*);','always #5 clk=~clk;','initial begin repeat(2) @(posedge clk); rst<=0;']
  for h,row in enumerate(rows):
    for k,v in enumerate(row['score_codes_q8_8']): lines.append(f'scores[{(h*32+k)*32} +: 32] <= {v};')
  prefix=lines; checks=[]
  for h,row in enumerate(rows):
    for k,v in enumerate(row['probabilities_q1_20']): checks.append(f'if (probabilities[{(h*32+k)*21} +: 21] !== {v}) begin $display("head {h} key {k} mismatch"); fail=fail+1; end')
  return '\n'.join(prefix+['@(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']+checks+['if(fail==0) $display("GPTNEO_SOFTMAX_SCHEDULER_16_ROWS_PASS"); else $fatal(1); $finish; end endmodule',''])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.write_text(generate(json.loads(a.reference.read_text())))
if __name__=='__main__':main()
