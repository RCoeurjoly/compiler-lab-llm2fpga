module RAM128X1S #(
  parameter [127:0] INIT = 128'h0
) (
  output O,
  input A0, A1, A2, A3, A4, A5, A6,
  input D, WCLK, WE
);
  wire lo, hi;
  RAMD64E #(.INIT(INIT[63:0])) lower (
    .CLK(WCLK), .I(D), .WE(WE & !A6), .O(lo),
    .RADR0(A0), .RADR1(A1), .RADR2(A2), .RADR3(A3), .RADR4(A4), .RADR5(A5),
    .WADR0(A0), .WADR1(A1), .WADR2(A2), .WADR3(A3), .WADR4(A4), .WADR5(A5),
    .WADR6(1'b0), .WADR7(1'b0)
  );
  RAMD64E #(.INIT(INIT[127:64])) upper (
    .CLK(WCLK), .I(D), .WE(WE & A6), .O(hi),
    .RADR0(A0), .RADR1(A1), .RADR2(A2), .RADR3(A3), .RADR4(A4), .RADR5(A5),
    .WADR0(A0), .WADR1(A1), .WADR2(A2), .WADR3(A3), .WADR4(A4), .WADR5(A5),
    .WADR6(1'b0), .WADR7(1'b0)
  );
  assign O = A6 ? hi : lo;
endmodule
