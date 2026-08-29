`timescale 1ns/1ps

// Serial Q·K score generator. Q/K are signed Q16.16; the contract emits
// signed Q8.8 scores by arithmetic right shift of the 64-bit dot product.
module llm2fpga_attention_scores_tensor #(
  parameter integer HEADS=16, parameter integer T=32, parameter integer HD=4
) (
  input wire clk,input wire rst,input wire start,input wire [4:0] position,
  input wire [HEADS*HD*32-1:0] query_q16,
  input wire [HEADS*T*HD*32-1:0] keys_q16,
  output reg done,output wire busy,output reg [HEADS*T*32-1:0] scores_q8
);
  localparam IDLE=2'd0,MAC=2'd1,EMIT=2'd2;
  reg [1:0] state; reg [4:0] head,key; reg [$clog2(HD)-1:0] dim;
  reg signed [63:0] accum; integer signed qv,kv; reg signed [63:0] product;
  assign busy=(state!=IDLE);
  always @(posedge clk) begin
    done<=0;
    if(rst) begin state<=IDLE; head<=0; key<=0; dim<=0; accum<=0; scores_q8<=0; end
    else case(state)
      IDLE: if(start) begin head<=0; key<=0; dim<=0; accum<=0; state<=MAC; end
      MAC: begin
        qv=$signed(query_q16[(head*HD+dim)*32 +: 32]);
        kv=$signed(keys_q16[((head*T+key)*HD+dim)*32 +: 32]);
        product=qv*kv; accum<=accum+product;
        if(dim==HD-1) state<=EMIT; else dim<=dim+1'b1;
      end
      EMIT: begin
        if(key<=position) scores_q8[(head*T+key)*32 +: 32] <= accum >>> 24;
        else scores_q8[(head*T+key)*32 +: 32] <= 0;
        accum<=0; dim<=0;
        if(key==T-1) begin key<=0; if(head==HEADS-1) begin done<=1; state<=IDLE; end else begin head<=head+1'b1; state<=MAC; end end
        else begin key<=key+1'b1; state<=MAC; end
      end
      default: state<=IDLE;
    endcase
  end
endmodule
