`timescale 1ns/1ps

// Packed tensor ABI for the compiler external call:
// tensor<16x32xi32> scores -> tensor<16x32xi32> probabilities.
// Scores use signed Q8.8 codes in 32-bit lanes; probabilities are unsigned
// Q1.20 values zero-extended in the low 21 bits of each 32-bit lane.
module llm2fpga_attention_softmax_fixed_tensor #(
    parameter EXP_FILE = "gptneo_exp.mem"
) (
    input  wire clk,
    input  wire rst,
    input  wire start,
    input  wire [31:0] position,
    input  wire [16*32*32-1:0] scores,
    output wire done,
    output wire busy,
    output wire [16*32*32-1:0] probabilities
);
  wire [16*32*21-1:0] packed_probabilities;
  wire [4:0] row_position = position[4:0];

  llm2fpga_attention_softmax_scheduler #(.EXP_FILE(EXP_FILE)) scheduler (
      .clk(clk), .rst(rst), .start(start), .position(row_position),
      .scores(scores), .done(done), .probabilities(packed_probabilities),
      .busy(busy));

  genvar lane;
  generate
    for (lane = 0; lane < 16*32; lane = lane + 1) begin : pack_probability
      assign probabilities[lane*32 +: 21] = packed_probabilities[lane*21 +: 21];
      assign probabilities[lane*32+21 +: 11] = 11'd0;
    end
  endgenerate
endmodule
