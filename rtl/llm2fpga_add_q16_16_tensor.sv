`timescale 1ns/1ps

// Packed tensor<64xi32> elementwise residual add. Arithmetic intentionally
// wraps at 32 bits, matching the fixed Q16.16 two's-complement contract.
module llm2fpga_add_q16_16_tensor #(parameter integer D = 64) (
    input wire clk, input wire rst, input wire start,
    input wire [D*32-1:0] lhs, input wire [D*32-1:0] rhs,
    output reg done, output wire busy,
    output reg [D*32-1:0] result
);
  reg active;
  integer i;
  assign busy = active;
  always @(posedge clk) begin
    done <= 1'b0;
    if (rst) begin active <= 1'b0; result <= 0; end
    else if (start && !active) begin
      for (i = 0; i < D; i = i + 1)
        result[i*32 +: 32] <= lhs[i*32 +: 32] + rhs[i*32 +: 32];
      active <= 1'b1;
    end else if (active) begin
      active <= 1'b0; done <= 1'b1;
    end
  end
endmodule
