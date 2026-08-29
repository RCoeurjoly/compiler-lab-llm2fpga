`timescale 1ns/1ps

// Composed attention path: Q/K score generation -> fixed softmax ->
// weighted-value context.  Projection and residual stages remain separate.
module llm2fpga_attention_block_tensor #(parameter EXP_FILE="gptneo_exp.mem") (
 input wire clk,input wire rst,input wire start,input wire [4:0] position,
 input wire [16*4*32-1:0] query_q16,input wire [16*32*4*32-1:0] keys_q16,
 input wire [16*32*4*32-1:0] values_q16,
 output reg done,output wire busy,output wire [16*4*32-1:0] context_q16
);
 localparam IDLE=2'd0,SCORE=2'd1,SOFT=2'd2,CTX=2'd3; reg [1:0] state; reg ss,sm,sc; wire ds,dm,dc; wire [16*32*32-1:0] scores; wire [16*32*32-1:0] probs;
 llm2fpga_attention_scores_tensor score(.clk(clk),.rst(rst),.start(ss),.position(position),.query_q16(query_q16),.keys_q16(keys_q16),.done(ds),.busy(),.scores_q8(scores));
 llm2fpga_attention_softmax_fixed_tensor #(.EXP_FILE(EXP_FILE)) softmax_i(.clk(clk),.rst(rst),.start(sm),.position({27'd0,position}),.scores(scores),.done(dm),.busy(),.probabilities(probs));
 llm2fpga_attention_context_tensor ctx(.clk(clk),.rst(rst),.start(sc),.position(position),.probabilities(probs),.values_q16(values_q16),.done(dc),.busy(),.context_q16(context_q16));
 assign busy=(state!=IDLE);
 always @(posedge clk) begin done<=0; ss<=0;sm<=0;sc<=0; if(rst) state<=IDLE; else case(state)
   IDLE: if(start) begin ss<=1; state<=SCORE; end
   SCORE: if(ds) begin sm<=1; state<=SOFT; end
   SOFT: if(dm) begin sc<=1; state<=CTX; end
   CTX: if(dc) begin done<=1; state<=IDLE; end
   default: state<=IDLE; endcase end
endmodule
