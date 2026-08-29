`timescale 1ns/1ps
// One-token transformer-block controller built from the verified subpaths.
module llm2fpga_transformer_block_tensor #(parameter EXP_FILE="gptneo_exp.mem", parameter GELU_FILE="gptneo_gelu.mem") (
 input wire clk,input wire rst,input wire start,input wire [4:0] position,
 input wire [2047:0] input_q16,ln1_gamma,ln1_beta,ln2_gamma,ln2_beta,
 input wire [65535:0] keys_q16,values_q16,
 input wire [1535:0] q_in_scales,q_out_scales,k_in_scales,k_out_scales,v_in_scales,v_out_scales,
 input wire [32767:0] q_weights,k_weights,v_weights,
 input wire [1535:0] q_weight_scales,k_weight_scales,v_weight_scales,
 input wire [2047:0] q_bias,k_bias,v_bias,
 input wire [1535:0] attn_in_scales,attn_weight_scales,attn_out_scales,input wire [32767:0] attn_weights,input wire [2047:0] attn_bias,
 input wire [1535:0] fc_in_input_scales,input wire [131071:0] fc_in_weights,input wire [6143:0] fc_in_weight_scales,fc_in_output_scales,input wire [8191:0] fc_in_bias,
 input wire [6143:0] fc_out_input_scales,input wire [131071:0] fc_out_weights,input wire [1535:0] fc_out_weight_scales,fc_out_output_scales,input wire [2047:0] fc_out_bias,
 output reg done,output wire busy,output wire [2047:0] output_q16
);
 localparam IDLE=3'd0,QKV=3'd1,ATTN=3'd2,LN2=3'd3,MLP=3'd4; reg [2:0] state; reg sq,sa,sl,sm; wire dq,da,dl,dm; wire [2047:0] q,k,v,attn_res,ln2,block_out;
 llm2fpga_qkv_frontend_tensor qkv(.clk(clk),.rst(rst),.start(sq),.input_q16(input_q16),.gamma_q16(ln1_gamma),.beta_q16(ln1_beta),.q_in_scales(q_in_scales),.q_out_scales(q_out_scales),.k_in_scales(k_in_scales),.k_out_scales(k_out_scales),.v_in_scales(v_in_scales),.v_out_scales(v_out_scales),.q_weights(q_weights),.k_weights(k_weights),.v_weights(v_weights),.q_weight_scales(q_weight_scales),.k_weight_scales(k_weight_scales),.v_weight_scales(v_weight_scales),.q_bias(q_bias),.k_bias(k_bias),.v_bias(v_bias),.done(dq),.busy(),.q_out(q),.k_out(k),.v_out(v));
 llm2fpga_attention_residual_tensor #(.EXP_FILE(EXP_FILE)) ar(.clk(clk),.rst(rst),.start(sa),.position(position),.query_q16(q),.keys_q16(keys_q16),.values_q16(values_q16),.input_scales_q24(attn_in_scales),.weights_q8(attn_weights),.weight_scales_q24(attn_weight_scales),.bias_q16(attn_bias),.output_scales_q24(attn_out_scales),.block_input_q16(input_q16),.done(da),.busy(),.residual_q16(attn_res));
 llm2fpga_fixed_layer_norm_q16_16_tensor ln(.clk(clk),.rst(rst),.start(sl),.input_values(attn_res),.gamma_values(ln2_gamma),.beta_values(ln2_beta),.done(dl),.busy(),.output_values(ln2));
 llm2fpga_mlp_block_tensor #(.LUT_FILE(GELU_FILE)) mlp(.clk(clk),.rst(rst),.start(sm),.ln2_q16(ln2),.attention_residual_q16(attn_res),.fc_in_input_scales_q24(fc_in_input_scales),.fc_in_weights_q8(fc_in_weights),.fc_in_weight_scales_q24(fc_in_weight_scales),.fc_in_bias_q16(fc_in_bias),.fc_in_output_scales_q24(fc_in_output_scales),.fc_out_input_scales_q24(fc_out_input_scales),.fc_out_weights_q8(fc_out_weights),.fc_out_weight_scales_q24(fc_out_weight_scales),.fc_out_bias_q16(fc_out_bias),.fc_out_output_scales_q24(fc_out_output_scales),.done(dm),.busy(),.output_q16(block_out));
 assign output_q16=block_out; assign busy=(state!=IDLE);
 always @(posedge clk) begin done<=0;sq<=0;sa<=0;sl<=0;sm<=0;if(rst)state<=IDLE;else case(state)
 IDLE:if(start)begin sq<=1;state<=QKV;end QKV:if(dq)begin sa<=1;state<=ATTN;end ATTN:if(da)begin sl<=1;state<=LN2;end LN2:if(dl)begin sm<=1;state<=MLP;end MLP:if(dm)begin done<=1;state<=IDLE;end default:state<=IDLE;endcase end
endmodule
