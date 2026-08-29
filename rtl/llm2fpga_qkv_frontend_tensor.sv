`timescale 1ns/1ps
// LN1 followed by serialized Q, K, V W8A8 projections.
module llm2fpga_qkv_frontend_tensor (
 input wire clk,input wire rst,input wire start,input wire [2047:0] input_q16,gamma_q16,beta_q16,
 input wire [1535:0] q_in_scales,q_out_scales,k_in_scales,k_out_scales,v_in_scales,v_out_scales,
 input wire [32767:0] q_weights,k_weights,v_weights,input wire [1535:0] q_weight_scales,k_weight_scales,v_weight_scales,
 input wire [2047:0] q_bias,k_bias,v_bias,
 output reg done,output wire busy,output reg [2047:0] q_out,k_out,v_out
);
 localparam IDLE=3'd0,LN=3'd1,Q=3'd2,K=3'd3,V=3'd4; reg [2:0] state; reg sl,sq,sk,sv; wire dl,dq,dk,dv; wire [2047:0] ln;
 llm2fpga_fixed_layer_norm_q16_16_tensor ln1(.clk(clk),.rst(rst),.start(sl),.input_values(input_q16),.gamma_values(gamma_q16),.beta_values(beta_q16),.done(dl),.busy(),.output_values(ln));
 llm2fpga_gemv_w8a8_tensor q(.clk(clk),.rst(rst),.start(sq),.activations_q16(ln),.input_scales_q24(q_in_scales),.weights_q8(q_weights),.weight_scales_q24(q_weight_scales),.bias_q16(q_bias),.output_scales_q24(q_out_scales),.done(dq),.busy(),.outputs_q16(q_out));
 llm2fpga_gemv_w8a8_tensor k(.clk(clk),.rst(rst),.start(sk),.activations_q16(ln),.input_scales_q24(k_in_scales),.weights_q8(k_weights),.weight_scales_q24(k_weight_scales),.bias_q16(k_bias),.output_scales_q24(k_out_scales),.done(dk),.busy(),.outputs_q16(k_out));
 llm2fpga_gemv_w8a8_tensor v(.clk(clk),.rst(rst),.start(sv),.activations_q16(ln),.input_scales_q24(v_in_scales),.weights_q8(v_weights),.weight_scales_q24(v_weight_scales),.bias_q16(v_bias),.output_scales_q24(v_out_scales),.done(dv),.busy(),.outputs_q16(v_out));
 assign busy=(state!=IDLE);
 always @(posedge clk) begin done<=0;sl<=0;sq<=0;sk<=0;sv<=0; if(rst) state<=IDLE; else case(state)
 IDLE:if(start)begin sl<=1;state<=LN;end LN:if(dl)begin sq<=1;state<=Q;end Q:if(dq)begin sk<=1;state<=K;end K:if(dk)begin sv<=1;state<=V;end V:if(dv)begin done<=1;state<=IDLE;end default:state<=IDLE;endcase end
endmodule
