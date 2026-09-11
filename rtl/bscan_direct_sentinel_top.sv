// Primitive-only BSCANE2 sentinel.  No system clock, CSR, or CDC is present;
// CAPTURE must load the marker and SHIFT must expose it LSB-first on TDO.
module bscan_direct_sentinel_top (
    input wire clk,
    output wire [2:0] led
);
  wire drck, reset, sel, shift, capture, update, tdi, tdo;
  wire runtest, tck, tms;
  reg [63:0] scan_reg;
  BSCANE2 #(.DISABLE_JTAG("FALSE"), .JTAG_CHAIN(1)) bscan (
      .CAPTURE(capture), .DRCK(drck), .RESET(reset), .RUNTEST(runtest),
      .SEL(sel), .SHIFT(shift), .TCK(tck), .TDI(tdi), .TDO(tdo),
      .TMS(tms), .UPDATE(update));
  always @(posedge drck or posedge reset) begin
    if (reset)
      scan_reg <= 64'd0;
    else if (sel && capture)
      scan_reg <= 64'hd3000000c0de5a17;
    else if (sel && shift)
      scan_reg <= {tdi, scan_reg[63:1]};
  end
  assign tdo = scan_reg[0];
  assign led = {clk, sel, capture};
endmodule
