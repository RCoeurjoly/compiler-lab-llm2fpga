`timescale 1ns/1ps

// Synthesis-only pressure shell for the compiler memory backend.  It exposes
// the logical request port and the exact audited UberDDR3 user-port shape;
// there is no model or accelerator claim in this shell.
module llm_ddr3_adapter_shell (
  input logic clk, input logic rst,
  input logic read_valid,
  input logic [31:0] read_address,
  output logic response_valid,
  output logic [7:0] response_data,
  output logic [31:0] response_address,
  output logic response_error,
  output logic wb_cyc, output logic wb_stb, output logic wb_we,
  output logic [31:0] wb_addr, output logic [15:0] wb_sel,
  input logic wb_accept, input logic wb_ack, input logic wb_err,
  input logic [127:0] wb_rdata
);
  llm_ddr3_adapter adapter (
    .clk(clk), .rst(rst), .read_valid(read_valid), .read_address(read_address),
    .response_valid(response_valid), .response_address(response_address),
    .response_data(response_data), .response_error(response_error),
    .wb_cyc(wb_cyc), .wb_stb(wb_stb),
    .wb_we(wb_we), .wb_addr(wb_addr), .wb_sel(wb_sel), .wb_accept(wb_accept),
    .wb_ack(wb_ack), .wb_err(wb_err), .wb_rdata(wb_rdata));
endmodule
