module top(input wire clk, input wire [29:0] a, input wire [17:0] b,
            output wire [47:0] y, output wire overflow);
  wire [47:0] p;
  DSP48E1 #(
    .ACASCREG(0), .ADREG(0), .A_INPUT("DIRECT"), .ALUMODEREG(0),
    .AREG(0), .BCASCREG(0), .B_INPUT("DIRECT"), .BREG(0),
    .CARRYINREG(0), .CARRYINSELREG(0), .CREG(0), .DREG(0),
    .INMODEREG(0), .MREG(1), .OPMODEREG(0), .PREG(0),
    .USE_MULT("MULTIPLY"), .USE_SIMD("ONE48"), .USE_DPORT("FALSE"),
    .OPMODE(7'b0000101)
  ) dsp (
    .CLK(clk), .A(a), .B(b), .C(48'b0), .D(25'b0),
    .INMODE(5'b0), .ALUMODE(4'b0), .OPMODE(7'b0000101),
    .CARRYINSEL(3'b0), .CARRYIN(1'b0), .PCIN(48'b0), .P(p)
  );
  reg [47:0] p_reg;
  always @(posedge clk) p_reg <= p;
  assign y = p_reg;
  assign overflow = (p_reg >= 48'h0000_8000_0000);
endmodule
