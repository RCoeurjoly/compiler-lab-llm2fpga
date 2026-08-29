`timescale 1ns/1ps

// External-call target for the compiler plugin.  The wrapper deliberately
// preserves the streaming score-row ABI of gptneo_softmax_only; tensor
// packing/unpacking remains a host/backend responsibility and is not hidden
// in this module.
module llm2fpga_attention_softmax_fixed #(
    parameter integer TMAX = 32,
    parameter EXP_FILE = "gptneo_exp.mem"
) (
    input wire clk, input wire rst,
    input wire start,
    input wire [4:0] position,
    input wire in_valid,
    output wire in_ready,
    input wire signed [31:0] in_score,
    output wire out_valid,
    input wire out_ready,
    output wire [4:0] out_index,
    output wire [20:0] out_probability,
    output wire busy
);
  gptneo_softmax_only #(.TMAX(TMAX), .EXP_FILE(EXP_FILE)) core (
      .clk(clk), .rst(rst), .start(start), .position(position),
      .in_valid(in_valid), .in_ready(in_ready), .in_score(in_score),
      .out_valid(out_valid), .out_ready(out_ready), .out_index(out_index),
      .out_probability(out_probability), .busy(busy));
endmodule
