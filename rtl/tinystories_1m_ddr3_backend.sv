`default_nettype none

// Transport-neutral boundary for the accepted compiler-generated
// TinyStories-1M accelerator.  The generated main owns the model schedule;
// this wrapper only joins its 240 immutable-memory ports to the audited
// single-outstanding 128-bit DDR3 Wishbone boundary.  PCIe and the physical
// UberDDR3 top remain outside this module.
module tinystories_1m_ddr3_backend #(
  parameter integer MEMORY_PORTS = 240,
  parameter integer WB_ADDR_BITS = 32,
  parameter integer WB_DATA_BITS = 128
) (
  input  wire                         clk,
  input  wire                         reset,
  input  wire                         start,
  input  wire                         valid,
  input  wire                         token_index,
  input  wire [15:0]                  prompt_0,
  input  wire [15:0]                  prompt_1,
  input  wire [15:0]                  prompt_2,
  input  wire [15:0]                  prompt_3,
  output wire                         done,
  output wire [15:0]                  token_id,
  output wire                         wb_cyc,
  output wire                         wb_stb,
  output wire                         wb_we,
  output wire [WB_ADDR_BITS-1:0]      wb_addr,
  output wire [WB_DATA_BITS/8-1:0]    wb_sel,
  input  wire                         wb_accept,
  input  wire                         wb_ack,
  input  wire                         wb_err,
  input  wire [WB_DATA_BITS-1:0]      wb_rdata
);
  // The externalizer's indexed ABI is deliberately explicit.  Keep the
  // parameter as an assertion/documentation aid; changing it without
  // regenerating main is rejected rather than silently truncating vectors.
  initial if (MEMORY_PORTS != 240 || WB_DATA_BITS != 128)
    $error("tinystories_1m_ddr3_backend requires 240 ports and 128-bit Wishbone");

  wire [239:0] ext_mem_req_valid;
  wire [239:0] ext_mem_req_ready;
  wire [7679:0] ext_mem_req_addr;
  wire [239:0] ext_mem_rsp_valid;
  wire [15359:0] ext_mem_rsp_data;

  // Preserve the compiler/transport cut during staged synthesis.  The
  // generated main and the audited arbiter must be lowered independently;
  // flattening them into the PCIe/DDR3 shell recreates the unbounded generic
  // process and arithmetic pass observed in the integration diagnostic.
  (* keep_hierarchy = "yes" *) main compiler_core (
    .start(start), .valid(valid), .token_index(token_index),
    .prompt_0(prompt_0), .prompt_1(prompt_1), .prompt_2(prompt_2),
    .prompt_3(prompt_3), .done(done), .token_id(token_id),
    .clk(clk), .reset(reset),
    .ext_mem_req_valid(ext_mem_req_valid),
    .ext_mem_req_ready(ext_mem_req_ready),
    .ext_mem_req_addr(ext_mem_req_addr),
    .ext_mem_rsp_valid(ext_mem_rsp_valid),
    .ext_mem_rsp_data(ext_mem_rsp_data)
  );

  wire arb_wb_cyc;
  wire arb_wb_stb;
  wire arb_wb_we;
  wire [WB_ADDR_BITS-1:0] arb_wb_addr;
  wire [WB_DATA_BITS/8-1:0] arb_wb_sel;
  wire arb_wb_accept;
  wire arb_wb_ack;
  wire arb_wb_err;
  wire [WB_DATA_BITS-1:0] arb_wb_rdata;

  (* keep_hierarchy = "yes" *) llm_external_memory_arbiter #(
    .PORTS(240), .ADDRESS_BITS(WB_ADDR_BITS), .DATA_BITS(64),
    .WB_DATA_BITS(128)
  ) memory_arbiter (
    .clk(clk), .rst(reset),
    .req_valid(ext_mem_req_valid), .req_ready(ext_mem_req_ready),
    .req_addr(ext_mem_req_addr), .rsp_valid(ext_mem_rsp_valid),
    .rsp_data(ext_mem_rsp_data), .wb_cyc(arb_wb_cyc), .wb_stb(arb_wb_stb),
    .wb_addr(arb_wb_addr), .wb_sel(arb_wb_sel), .wb_accept(arb_wb_accept),
    .wb_ack(arb_wb_ack), .wb_err(arb_wb_err), .wb_rdata(arb_wb_rdata)
  );

  // The generated memory contract is read-only.  The arbiter intentionally
  // has no write-enable output, so make that invariant explicit at the
  // Wishbone boundary instead of leaving an undriven control net.
  assign arb_wb_we = 1'b0;

  // Register the compiler/DDR owner boundary. This preserves the external
  // memory ABI while preventing the 240-way compiler arbiter from driving the
  // physical DDR controller's acceptance path combinationally.
  (* keep_hierarchy = "yes" *) llm_wishbone_pipeline #(
    .ADDRESS_BITS(WB_ADDR_BITS), .DATA_BITS(WB_DATA_BITS)
  ) memory_wishbone_pipeline (
    .clk(clk), .rst(reset),
    .m_cyc(arb_wb_cyc), .m_stb(arb_wb_stb), .m_we(arb_wb_we),
    .m_addr(arb_wb_addr), .m_sel(arb_wb_sel),
    .m_accept(arb_wb_accept), .m_ack(arb_wb_ack), .m_err(arb_wb_err),
    .m_rdata(arb_wb_rdata),
    .s_cyc(wb_cyc), .s_stb(wb_stb), .s_we(wb_we), .s_addr(wb_addr),
    .s_sel(wb_sel), .s_accept(wb_accept), .s_ack(wb_ack), .s_err(wb_err),
    .s_rdata(wb_rdata)
  );
endmodule

`default_nettype wire
