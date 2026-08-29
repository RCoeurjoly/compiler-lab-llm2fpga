`timescale 1ns/1ps
// Complete attention subgraph: Q/K/V -> score/softmax/context -> out GEMV -> residual.
module llm2fpga_attention_residual_tensor #(parameter EXP_FILE="gptneo_exp.mem") (
 input wire clk,input wire rst,input wire start,input wire [4:0] position,
 input wire [2047:0] query_q16,input wire [65535:0] keys_q16,input wire [65535:0] values_q16,
 input wire [1535:0] input_scales_q24, input wire [32767:0] weights_q8,
 input wire [1535:0] weight_scales_q24, input wire [2047:0] bias_q16, input wire [1535:0] output_scales_q24,
 input wire [2047:0] block_input_q16, output reg done, output wire busy, output wire [2047:0] residual_q16
);
 localparam IDLE=2'd0,ATTN=2'd1,PROJ=2'd2,S_ADD=2'd3; reg [1:0] state; reg sa,sp,sr; wire da,dp,dr; wire [2047:0] attn_context; wire [2047:0] projected;
 llm2fpga_attention_block_tensor #(.EXP_FILE(EXP_FILE)) attn(.clk(clk),.rst(rst),.start(sa),.position(position),.query_q16(query_q16),.keys_q16(keys_q16),.values_q16(values_q16),.done(da),.busy(),.context_q16(attn_context));
 llm2fpga_gemv_w8a8_tensor #(.M(64),.K(64)) proj(.clk(clk),.rst(rst),.start(sp),.activations_q16(attn_context),.input_scales_q24(input_scales_q24),.weights_q8(weights_q8),.weight_scales_q24(weight_scales_q24),.bias_q16(bias_q16),.output_scales_q24(output_scales_q24),.done(dp),.busy(),.outputs_q16(projected));
 llm2fpga_add_q16_16_tensor add(.clk(clk),.rst(rst),.start(sr),.lhs(block_input_q16),.rhs(projected),.done(dr),.busy(),.result(residual_q16));
 assign busy=(state!=IDLE);
 always @(posedge clk) begin done<=0;sa<=0;sp<=0;sr<=0; if(rst) state<=IDLE; else case(state)
 IDLE: if(start) begin sa<=1;state<=ATTN;end
 ATTN: if(da) begin sp<=1;state<=PROJ;end
 PROJ: if(dp) begin sr<=1;state<=S_ADD;end
 S_ADD: if(dr) begin done<=1;state<=IDLE;end
 default: state<=IDLE; endcase end
endmodule
