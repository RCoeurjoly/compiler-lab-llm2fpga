#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
import numpy as np
def u(v,b): return int(v)&((1<<b)-1)
def emit_vec(out,name,vals,bits):
    for i,v in enumerate(np.asarray(vals).reshape(-1)): out.append(f'{name}[{i*bits} +: {bits}] <= {u(v,bits)};')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--package',type=Path,required=True); ap.add_argument('--oracle',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--lut',type=Path,required=True); a=ap.parse_args()
    sys.path.insert(0,'/home/roland/kev-gpt/.worktrees/kintex-selftest'); from tinystories.int_reference import IntegerGPTNeo
    p=IntegerGPTNeo(a.package); o=json.loads(a.oracle.read_text())['oracle']['checkpoints']; ln2=o['block.ln_2.output']['values']; residual=o['block.residual.attention']['values']; expected=o['block.output']['values']
    def scales(k): return np.rint(p.activation_scales[k]*(1<<24)).astype(np.int64)
    wi=p.tensor_codes['blocks.0.mlp.fc.weight']; si=np.rint(p.tensor_scales['blocks.0.mlp.fc.weight']*(1<<24)).astype(np.int64); bi=np.rint(p.tensors['blocks.0.mlp.fc.bias']*(1<<16)).astype(np.int64); oi=scales('transformer.h.0.mlp.c_fc.output'); ii=scales('transformer.h.0.mlp.c_fc.input')
    wo=p.tensor_codes['blocks.0.mlp.proj.weight']; so=np.rint(p.tensor_scales['blocks.0.mlp.proj.weight']*(1<<24)).astype(np.int64); bo=np.rint(p.tensors['blocks.0.mlp.proj.bias']*(1<<16)).astype(np.int64); io=scales('transformer.h.0.mlp.c_proj.input'); oo=scales('transformer.h.0.mlp.c_proj.output')
    out=['`timescale 1ns/1ps','module tb_mlp_comp; reg clk=0,rst=1,start=0; reg [2047:0] ln2_q16=0,attention_residual_q16=0; reg [1535:0] fc_in_input_scales_q24=0,fc_out_weight_scales_q24=0,fc_out_output_scales_q24=0; reg [6143:0] fc_in_weight_scales_q24=0,fc_in_output_scales_q24=0,fc_out_input_scales_q24=0; reg [131071:0] fc_in_weights_q8=0; reg [131071:0] fc_out_weights_q8=0; reg [8191:0] fc_in_bias_q16=0; reg [2047:0] fc_out_bias_q16=0; wire done,busy; wire [2047:0] output_q16;','llm2fpga_mlp_block_tensor #(.LUT_FILE("/tmp/gptneo_gelu.mem")) dut(.*); always #5 clk=~clk; initial begin repeat(2) @(posedge clk); rst<=0;']
    emit_vec(out,'ln2_q16',ln2,32); emit_vec(out,'attention_residual_q16',residual,32); emit_vec(out,'fc_in_input_scales_q24',ii,24); emit_vec(out,'fc_in_weights_q8',wi.reshape(-1),8); emit_vec(out,'fc_in_weight_scales_q24',si,24); emit_vec(out,'fc_in_bias_q16',bi,32); emit_vec(out,'fc_in_output_scales_q24',oi,24); emit_vec(out,'fc_out_input_scales_q24',io,24); emit_vec(out,'fc_out_weights_q8',wo.reshape(-1),8); emit_vec(out,'fc_out_weight_scales_q24',so,24); emit_vec(out,'fc_out_bias_q16',bo,32); emit_vec(out,'fc_out_output_scales_q24',oo,24)
    out += ['repeat(2) @(posedge clk); start<=1; @(posedge clk); start<=0; wait(done); @(posedge clk);']
    for i,v in enumerate(expected): out.append(f'if (output_q16[{i*32} +: 32] !== {u(v,32)}) begin $display("lane {i} mismatch"); $fatal; end')
    out += ['$display("LLM2FPGA_MLP_COMPOSITION_PASS"); $finish; end endmodule','']; a.output.write_text('\n'.join(out))
if __name__=='__main__': main()
