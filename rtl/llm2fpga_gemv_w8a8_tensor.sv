`timescale 1ns/1ps

// Contract-bound serial W8A8 GEMV adapter. Inputs/outputs are packed
// little-endian lanes; arithmetic follows tinystories-1m-gemv-contract-v1.
module llm2fpga_gemv_w8a8_tensor #(parameter integer M=64, parameter integer K=64) (
  input wire clk, input wire rst, input wire start,
  input wire [K*32-1:0] activations_q16,
  input wire [K*24-1:0] input_scales_q24,
  input wire [M*K*8-1:0] weights_q8,
  input wire [M*24-1:0] weight_scales_q24,
  input wire [M*32-1:0] bias_q16,
  input wire [M*24-1:0] output_scales_q24,
  output reg done, output wire busy, output reg [M*32-1:0] outputs_q16
);
  localparam IDLE=2'd0, MAC=2'd1, EMIT=2'd2;
  reg [1:0] state; reg [$clog2(M)-1:0] row; reg [$clog2(K)-1:0] col;
  reg signed [63:0] accum;
  integer signed av, ins, code, w, ws, os, b;
  reg signed [63:0] term, real_q16, out_code, magnitude;
  function automatic signed [63:0] round_shift32(input signed [127:0] value);
    reg signed [127:0] mag;
    begin mag = value < 0 ? -value : value; mag = (mag + (128'sd1 <<< 31)) >>> 32; round_shift32 = value < 0 ? -mag : mag; end
  endfunction
  function automatic signed [63:0] round_shift8(input signed [63:0] value);
    reg signed [63:0] mag;
    begin mag = value < 0 ? -value : value; mag = (mag + 64'sd128) >>> 8; round_shift8 = value < 0 ? -mag : mag; end
  endfunction
  function automatic signed [63:0] activation_code(input signed [63:0] value, input signed [63:0] scale);
    reg signed [63:0] n, mag, q;
    begin n=value<<<8; mag=n<0?-n:n; q=(mag+(scale>>>1))/scale; if(n<0) q=-q; if(q>127) q=127; if(q < -128) q=-128; activation_code=q; end
  endfunction
  assign busy = (state != IDLE);
  always @(posedge clk) begin
    done <= 1'b0;
    if (rst) begin state<=IDLE; row<=0; col<=0; accum<=0; outputs_q16<=0; end
    else case(state)
      IDLE: if(start) begin row<=0; col<=0; accum<=0; state<=MAC; end
      MAC: begin
        av = $signed(activations_q16[col*32 +: 32]);
        ins = $unsigned(input_scales_q24[col*24 +: 24]);
        code = activation_code(av, ins);
        w = $signed(weights_q8[(row*K+col)*8 +: 8]);
        term = code * ins * w;
        if(col == K-1) begin
          accum <= accum + term; state<=EMIT;
        end else begin accum <= accum + term; col<=col+1'b1; end
      end
      EMIT: begin
        ws = $unsigned(weight_scales_q24[row*24 +: 24]);
        os = $unsigned(output_scales_q24[row*24 +: 24]);
        b = $signed(bias_q16[row*32 +: 32]);
        real_q16 = round_shift32((accum * ws)) + b;
        out_code = activation_code(real_q16, os);
        outputs_q16[row*32 +: 32] <= round_shift8(out_code * os);
        if(row == M-1) begin done<=1'b1; state<=IDLE; end
        else begin row<=row+1'b1; col<=0; accum<=0; state<=MAC; end
      end
    endcase
  end
endmodule
