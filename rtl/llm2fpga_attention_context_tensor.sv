`timescale 1ns/1ps

// Causal attention context: probabilities are unsigned Q1.20 and values are
// signed Q16.16.  The serial reduction truncates the product sum by 20 bits.
module llm2fpga_attention_context_tensor #(
  parameter integer HEADS=16, parameter integer T=32, parameter integer HD=4
) (
  input wire clk,input wire rst,input wire start,input wire [4:0] position,
  input wire [HEADS*T*32-1:0] probabilities,
  input wire [HEADS*T*HD*32-1:0] values_q16,
  output reg done, output wire busy, output reg [HEADS*HD*32-1:0] context_q16
);
  localparam IDLE=2'd0,REDUCE=2'd1,EMIT=2'd2;
  reg [1:0] state; reg [4:0] head,key; reg [$clog2(HD)-1:0] dim;
  reg signed [63:0] accum; integer signed prob,val; reg signed [63:0] product;
  function automatic signed [63:0] round_context(input signed [63:0] x);
    reg signed [63:0] m; begin m=x<0?-x:x; m=(m+64'sd524288)>>>20; round_context=x<0?-m:m; end
  endfunction
  assign busy=(state!=IDLE);
  always @(posedge clk) begin
    done<=0;
    if(rst) begin state<=IDLE; head<=0; key<=0; dim<=0; accum<=0; context_q16<=0; end
    else case(state)
      IDLE: if(start) begin head<=0; dim<=0; key<=0; accum<=0; state<=REDUCE; end
      REDUCE: begin
        prob=$unsigned(probabilities[(head*T+key)*32 +: 21]);
        val=$signed(values_q16[((head*T+key)*HD+dim)*32 +: 32]);
        product=prob*val;
        if(key<=position) begin accum<=accum+product; key<=key+1'b1; end
        else begin key<=key+1'b1; end
        if(key==T-1) state<=EMIT;
      end
      EMIT: begin
        context_q16[(head*HD+dim)*32 +: 32] <= round_context(accum);
        accum<=0; key<=0;
        if(dim==HD-1) begin dim<=0; if(head==HEADS-1) begin done<=1; state<=IDLE; end else begin head<=head+1'b1; state<=REDUCE; end end
        else begin dim<=dim+1'b1; state<=REDUCE; end
      end
      default: state<=IDLE;
    endcase
  end
endmodule
