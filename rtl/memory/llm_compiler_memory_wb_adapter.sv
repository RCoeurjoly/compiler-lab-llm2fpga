`default_nettype none

// Transport-only adapter for compiler-generated memory ports.
//
// The generated RC exposes one read request per logical immutable memory.  The
// adapter keeps those ports independent at the compiler boundary, then uses
// the validated single-outstanding arbiter to present one 128-bit Wishbone
// read port to UberDDR3.  It contains no model arithmetic or copied
// accelerator RTL.
module llm_compiler_memory_wb_adapter #(
  parameter int PORTS = 55,
  parameter int ADDRESS_BITS = 32,
  parameter int DATA_BITS = 64,
  parameter int WB_DATA_BITS = 128
) (
  input  logic clk,
  input  logic rst,
  input  logic [PORTS-1:0] req_valid,
  output logic [PORTS-1:0] req_ready,
  input  logic [PORTS*ADDRESS_BITS-1:0] req_addr,
  output logic [PORTS-1:0] rsp_valid,
  output logic [PORTS*DATA_BITS-1:0] rsp_data,
  output logic wb_cyc,
  output logic wb_stb,
  output logic [ADDRESS_BITS-1:0] wb_addr,
  output logic [WB_DATA_BITS/8-1:0] wb_sel,
  input logic wb_accept,
  input logic wb_ack,
  input logic wb_err,
  input logic [WB_DATA_BITS-1:0] wb_rdata
);
  llm_external_memory_arbiter #(
    .PORTS(PORTS),
    .ADDRESS_BITS(ADDRESS_BITS),
    .DATA_BITS(DATA_BITS),
    .WB_DATA_BITS(WB_DATA_BITS)
  ) arbiter (
    .clk(clk), .rst(rst),
    .req_valid(req_valid), .req_ready(req_ready), .req_addr(req_addr),
    .rsp_valid(rsp_valid), .rsp_data(rsp_data),
    .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_addr(wb_addr), .wb_sel(wb_sel),
    .wb_accept(wb_accept), .wb_ack(wb_ack), .wb_err(wb_err),
    .wb_rdata(wb_rdata)
  );
endmodule

`default_nettype wire
