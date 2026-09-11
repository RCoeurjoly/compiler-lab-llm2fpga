// Primitive-only BSCANE2 sentinel.  No system clock, CSR, or CDC is present;
// CAPTURE must load the marker and SHIFT must expose it LSB-first on TDO.
module bscan_direct_sentinel_top (
    input wire clk,
    output wire [2:0] led
);
  wire drck, reset, sel, shift, capture, update, tdi, tdo;
  wire runtest, tck, tms;
  BSCANE2 #(.DISABLE_JTAG("FALSE"), .JTAG_CHAIN(1)) bscan (
      .CAPTURE(capture), .DRCK(drck), .RESET(reset), .RUNTEST(runtest),
      .SEL(sel), .SHIFT(shift), .TCK(tck), .TDI(tdi), .TDO(tdo),
      .TMS(tms), .UPDATE(update));
  // TDO control: SEL is high throughout USER1 Capture/Shift, so this should
  // read as all ones while selected without any scan-register state.
  assign tdo = sel;
  assign led = {clk, sel, capture};
endmodule
