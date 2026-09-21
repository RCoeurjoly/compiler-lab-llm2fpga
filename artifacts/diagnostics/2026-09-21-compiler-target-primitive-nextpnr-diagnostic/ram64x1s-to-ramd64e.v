module RAM64X1S #(
  parameter [63:0] INIT = 64'h0
) (
  output O,
  input A0, A1, A2, A3, A4, A5,
  input D, WCLK, WE
);
  RAMD64E #(.INIT(INIT)) _TECHMAP_REPLACE_ (
    .CLK(WCLK), .I(D), .WE(WE), .O(O),
    .RADR0(A0), .RADR1(A1), .RADR2(A2), .RADR3(A3), .RADR4(A4), .RADR5(A5),
    .WADR0(A0), .WADR1(A1), .WADR2(A2), .WADR3(A3), .WADR4(A4), .WADR5(A5),
    .WADR6(1'b0), .WADR7(1'b0)
  );
endmodule
