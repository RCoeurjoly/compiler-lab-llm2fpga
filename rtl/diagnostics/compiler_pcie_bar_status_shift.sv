// SPDX-License-Identifier: AGPL-3.0-or-later
`default_nettype none

// Persistent USER4 observer for the PCIe-converter/accelerator BAR boundary.
// Counting both valid cycles and completed handshakes distinguishes a decoder
// that never issues work from downstream backpressure and response starvation.
module compiler_pcie_bar_status_shift #(
  parameter integer WIDTH = 320,
  parameter integer JTAG_CHAIN = 4
) (
  input wire clk_i,
  input wire rst_n_i,
  input wire [31:0] bar_araddr_i,
  input wire bar_arvalid_i,
  input wire bar_arready_i,
  input wire [31:0] bar_rdata_i,
  input wire bar_rvalid_i,
  input wire bar_rready_i,
  input wire [31:0] bar_awaddr_i,
  input wire bar_awvalid_i,
  input wire bar_awready_i,
  input wire [31:0] bar_wdata_i,
  input wire bar_wvalid_i,
  input wire bar_wready_i,
  input wire bar_bvalid_i,
  input wire bar_bready_i
);
  localparam [31:0] MAGIC = 32'h43504253; // CPBS
  localparam [7:0] VERSION = 8'd2;

  reg [23:0] clk_count_q = 0;
  reg [15:0] reset_seen_q = 0;
  reg [31:0] arvalid_count_q = 0;
  reg [31:0] ar_count_q = 0;
  reg [31:0] rvalid_count_q = 0;
  reg [31:0] r_count_q = 0;
  reg [31:0] last_araddr_q = 0;
  reg [31:0] last_rdata_q = 0;
  reg [15:0] sticky_q = 0;

  always @(posedge clk_i) begin
    clk_count_q <= clk_count_q + 1;
    if (!rst_n_i) begin
      reset_seen_q <= reset_seen_q + 1;
      arvalid_count_q <= 0; ar_count_q <= 0;
      rvalid_count_q <= 0; r_count_q <= 0;
      last_araddr_q <= 0; last_rdata_q <= 0;
      sticky_q <= 0;
    end else begin
      if (bar_arvalid_i) begin arvalid_count_q <= arvalid_count_q + 1; sticky_q[0] <= 1; end
      if (bar_arvalid_i && bar_arready_i) begin
        ar_count_q <= ar_count_q + 1; last_araddr_q <= bar_araddr_i; sticky_q[1] <= 1;
      end
      if (bar_rvalid_i) begin rvalid_count_q <= rvalid_count_q + 1; last_rdata_q <= bar_rdata_i; sticky_q[2] <= 1; end
      if (bar_rvalid_i && bar_rready_i) begin r_count_q <= r_count_q + 1; sticky_q[3] <= 1; end
      if (bar_awvalid_i) sticky_q[4] <= 1;
      if (bar_awvalid_i && bar_awready_i) sticky_q[5] <= 1;
      if (bar_wvalid_i) sticky_q[6] <= 1;
      if (bar_wvalid_i && bar_wready_i) sticky_q[7] <= 1;
      if (bar_bvalid_i) sticky_q[8] <= 1;
      if (bar_bvalid_i && bar_bready_i) sticky_q[9] <= 1;
      if (bar_arready_i) sticky_q[10] <= 1;
      if (bar_rready_i) sticky_q[11] <= 1;
      if (bar_awready_i) sticky_q[12] <= 1;
      if (bar_wready_i) sticky_q[13] <= 1;
      if (bar_bready_i) sticky_q[14] <= 1;
    end
  end

  wire [15:0] flags_word = {
    5'd0, bar_bready_i, bar_bvalid_i, bar_wready_i, bar_wvalid_i,
    bar_awready_i, bar_awvalid_i, bar_rready_i, bar_rvalid_i,
    bar_arready_i, bar_arvalid_i, rst_n_i
  };
  wire [WIDTH-1:0] payload_fixed = '0
    | ({{(WIDTH-32){1'b0}}, MAGIC} << 0)
    | ({{(WIDTH-8){1'b0}}, VERSION} << 32)
    | ({{(WIDTH-16){1'b0}}, flags_word} << 40)
    | ({{(WIDTH-24){1'b0}}, clk_count_q} << 56)
    | ({{(WIDTH-32){1'b0}}, arvalid_count_q} << 80)
    | ({{(WIDTH-32){1'b0}}, ar_count_q} << 112)
    | ({{(WIDTH-32){1'b0}}, rvalid_count_q} << 144)
    | ({{(WIDTH-32){1'b0}}, r_count_q} << 176)
    | ({{(WIDTH-32){1'b0}}, last_araddr_q} << 208)
    | ({{(WIDTH-32){1'b0}}, last_rdata_q} << 240)
    | ({{(WIDTH-16){1'b0}}, sticky_q} << 272)
    | ({{(WIDTH-16){1'b0}}, reset_seen_q} << 288);

  wire capture, drck, reset, runtest, sel, shift, tck, tdi, tms, update;
  wire tdo;
  reg [WIDTH-1:0] shift_q = 0;
  assign tdo = shift_q[0];
  always @(posedge drck or posedge reset) begin
    if (reset) shift_q <= 0;
    else if (sel && capture) shift_q <= payload_fixed;
    else if (sel && shift) shift_q <= {tdi, shift_q[WIDTH-1:1]};
  end
  BSCANE2 #(.DISABLE_JTAG("FALSE"), .JTAG_CHAIN(JTAG_CHAIN)) bscan (
    .CAPTURE(capture), .DRCK(drck), .RESET(reset), .RUNTEST(runtest),
    .SEL(sel), .SHIFT(shift), .TCK(tck), .TDI(tdi), .TMS(tms),
    .UPDATE(update), .TDO(tdo)
  );
  wire unused = &{1'b0, runtest, tck, tms, update};
endmodule

`default_nettype wire
