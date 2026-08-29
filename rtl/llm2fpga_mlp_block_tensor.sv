`timescale 1ns/1ps

// Composed fixed-point MLP/residual path for one transformer block.
// Inputs are the authenticated LN2 and attention-residual checkpoints;
// projection arithmetic is delegated to the contract-bound GEMV adapter.
module llm2fpga_mlp_block_tensor #(
  parameter integer D=64, parameter integer H=256,
  parameter LUT_FILE="gptneo_gelu.mem"
) (
  input wire clk,input wire rst,input wire start,
  input wire [D*32-1:0] ln2_q16, input wire [D*32-1:0] attention_residual_q16,
  input wire [D*24-1:0] fc_in_input_scales_q24,
  input wire [H*D*8-1:0] fc_in_weights_q8,
  input wire [H*24-1:0] fc_in_weight_scales_q24,
  input wire [H*32-1:0] fc_in_bias_q16,
  input wire [H*24-1:0] fc_in_output_scales_q24,
  input wire [H*24-1:0] fc_out_input_scales_q24,
  input wire [D*H*8-1:0] fc_out_weights_q8,
  input wire [D*24-1:0] fc_out_weight_scales_q24,
  input wire [D*32-1:0] fc_out_bias_q16,
  input wire [D*24-1:0] fc_out_output_scales_q24,
  output reg done, output wire busy, output reg [D*32-1:0] output_q16
);
  localparam S_IDLE=3'd0,S_FCIN=3'd1,S_GELU=3'd2,S_FCOUT=3'd3,S_RESID=3'd4;
  reg [2:0] state;
  reg s_fcin,s_gelu,s_fcout,s_resid;
  wire d_fcin,d_gelu,d_fcout,d_resid;
  wire [H*32-1:0] fcin_q16, gelu_q16;
  wire [D*32-1:0] fcout_q16, residual_q16;
  llm2fpga_gemv_w8a8_tensor #(.M(H),.K(D)) fcin(.clk(clk),.rst(rst),.start(s_fcin),.activations_q16(ln2_q16),.input_scales_q24(fc_in_input_scales_q24),.weights_q8(fc_in_weights_q8),.weight_scales_q24(fc_in_weight_scales_q24),.bias_q16(fc_in_bias_q16),.output_scales_q24(fc_in_output_scales_q24),.done(d_fcin),.busy(),.outputs_q16(fcin_q16));
  llm2fpga_gelu_q16_tensor #(.D(H),.LUT_FILE(LUT_FILE)) gelu(.clk(clk),.rst(rst),.start(s_gelu),.inputs_q16(fcin_q16),.done(d_gelu),.busy(),.outputs_q16(gelu_q16));
  llm2fpga_gemv_w8a8_tensor #(.M(D),.K(H)) fcout(.clk(clk),.rst(rst),.start(s_fcout),.activations_q16(gelu_q16),.input_scales_q24(fc_out_input_scales_q24),.weights_q8(fc_out_weights_q8),.weight_scales_q24(fc_out_weight_scales_q24),.bias_q16(fc_out_bias_q16),.output_scales_q24(fc_out_output_scales_q24),.done(d_fcout),.busy(),.outputs_q16(fcout_q16));
  llm2fpga_add_q16_16_tensor #(.D(D)) residual(.clk(clk),.rst(rst),.start(s_resid),.lhs(attention_residual_q16),.rhs(fcout_q16),.done(d_resid),.busy(),.result(residual_q16));
  assign busy=(state!=S_IDLE);
  always @(posedge clk) begin
    done<=0; s_fcin<=0; s_gelu<=0; s_fcout<=0; s_resid<=0;
    if(rst) begin state<=S_IDLE; output_q16<=0; end
    else case(state)
      S_IDLE: if(start) begin s_fcin<=1; state<=S_FCIN; end
      S_FCIN: if(d_fcin) begin s_gelu<=1; state<=S_GELU; end
      S_GELU: if(d_gelu) begin s_fcout<=1; state<=S_FCOUT; end
      S_FCOUT: if(d_fcout) begin s_resid<=1; state<=S_RESID; end
      S_RESID: if(d_resid) begin output_q16<=residual_q16; done<=1; state<=S_IDLE; end
      default: state<=S_IDLE;
    endcase
  end
endmodule
