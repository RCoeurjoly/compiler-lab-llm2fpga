// Compatibility map for the pinned nextpnr-xilinx Kintex-7 flow.
// The mapper accepts these single-port distributed-RAM cells, but the
// nextpnr packer requires the corresponding dual-port primitive templates.
module RAM64X1S(output O, input A0, A1, A2, A3, A4, A5,
                input D, WCLK, WE);
  parameter [63:0] INIT = 64'h0;
  parameter IS_WCLK_INVERTED = 1'b0;
  wire unused_dpo;
  RAM64X1D #(.INIT(INIT), .IS_WCLK_INVERTED(IS_WCLK_INVERTED))
    _TECHMAP_REPLACE_ (
      .SPO(O), .DPO(unused_dpo), .D(D), .WCLK(WCLK), .WE(WE),
      .A0(A0), .A1(A1), .A2(A2), .A3(A3), .A4(A4), .A5(A5),
      .DPRA0(A0), .DPRA1(A1), .DPRA2(A2), .DPRA3(A3),
      .DPRA4(A4), .DPRA5(A5));
endmodule

module RAM128X1S(output O, input A0, A1, A2, A3, A4, A5, A6,
                 input D, WCLK, WE);
  parameter [127:0] INIT = 128'h0;
  parameter IS_WCLK_INVERTED = 1'b0;
  wire unused_dpo;
  wire [6:0] addr = {A6, A5, A4, A3, A2, A1, A0};
  RAM128X1D #(.INIT(INIT), .IS_WCLK_INVERTED(IS_WCLK_INVERTED))
    _TECHMAP_REPLACE_ (
      .SPO(O), .DPO(unused_dpo), .D(D), .WCLK(WCLK), .WE(WE),
      .A(addr), .DPRA(addr));
endmodule
