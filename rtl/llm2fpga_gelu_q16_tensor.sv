`timescale 1ns/1ps

// Packed Q16.16 GELU adapter. The reference LUT operates on rounded Q4.12;
// results are shifted back to Q16.16 after interpolation.
module llm2fpga_gelu_q16_tensor #(parameter integer D=256, parameter LUT_FILE="gptneo_gelu.mem") (
  input wire clk,input wire rst,input wire start,
  input wire [D*32-1:0] inputs_q16,
  output reg done,output wire busy,output reg [D*32-1:0] outputs_q16
);
  localparam IDLE=2'd0,SEND=2'd1,RECV=2'd2;
  reg [1:0] state; reg [$clog2(D)-1:0] index;
  wire in_ready,out_valid; wire signed [15:0] out_data;
  reg in_valid; wire signed [15:0] in_data;
  reg signed [31:0] q12;
  reg signed [31:0] raw_q16;
  always @* begin
    raw_q16 = $signed(inputs_q16[index*32 +: 32]);
    // Match hardware_reference.round_shift: nearest, ties away from zero.
    if (raw_q16 < 0) q12 = -(((-raw_q16) + 32'sd8) >>> 4);
    else q12 = (raw_q16 + 32'sd8) >>> 4;
    if (q12 > 32767) q12 = 32767; else if (q12 < -32768) q12 = -32768;
  end
  assign in_data = q12[15:0];
  gptneo_gelu #(.LUT_FILE(LUT_FILE)) core(.clk(clk),.rst(rst),.in_valid(in_valid),.in_ready(in_ready),.in_data(in_data),.out_valid(out_valid),.out_ready(1'b1),.out_data(out_data),.debug_state());
  assign busy = (state != IDLE);
  always @(posedge clk) begin
    done<=0; in_valid<=0;
    if(rst) begin state<=IDLE; index<=0; outputs_q16<=0; end
    else case(state)
      IDLE: if(start) begin index<=0; state<=SEND; end
      SEND: if(in_ready) begin in_valid<=1; state<=RECV; end
      RECV: if(out_valid) begin outputs_q16[index*32 +: 32] <= $signed(out_data) <<< 4; if(index==D-1) begin done<=1; state<=IDLE; end else begin index<=index+1'b1; state<=SEND; end end
    endcase
  end
endmodule
