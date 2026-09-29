module gold #(parameter [63:0] INIT = 64'h0,
              parameter IS_WCLK_INVERTED = 1'b0)
  (input wire WCLK, WE, D, input wire [5:0] A, output wire O);
  RAM64X1S #(.INIT(INIT), .IS_WCLK_INVERTED(IS_WCLK_INVERTED)) ram
    (.O(O), .D(D), .WE(WE), .WCLK(WCLK),
     .A0(A[0]), .A1(A[1]), .A2(A[2]), .A3(A[3]), .A4(A[4]), .A5(A[5]));
endmodule
