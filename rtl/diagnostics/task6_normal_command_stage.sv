`default_nettype none
// One rowstream-clock boundary after the unchanged PCIe/JTAG priority mux.
// Acceptance is an input-cycle decision: a busy event must never become a
// newly accepted command when the sequencer becomes idle on the next edge.
module task6_normal_command_stage #(
  parameter integer WB_SEL_BITS = 16
) (
  input wire clk, rst_n, enabled,
  input wire [207:0] payload,
  input wire event_i, accept_phase, idle, ready, busy, source_pcie,
  output reg [207:0] payload_q,
  output reg event_q, source_pcie_q, accept_q, restart_q,
  output reg [19:1] decode_q
);
  wire eligible = enabled && event_i && !accept_phase && idle;
  wire accepted = eligible && payload[31:0] == 32'h33445244 && ready && !busy;
  wire chunk_zero = payload[41:40] == 2'd0;
  wire [7:0] opcode = payload[39:32];
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      payload_q <= 208'd0;
      event_q <= 1'b0;
      source_pcie_q <= 1'b0;
      accept_q <= 1'b0;
      restart_q <= 1'b0;
      decode_q <= 19'd0;
    end else begin
      event_q <= enabled && event_i;
      accept_q <= accepted;
      restart_q <= eligible && !accepted;
      if (enabled && event_i) begin
        payload_q <= payload;
        source_pcie_q <= source_pcie;
        decode_q[1] <= opcode == 8'h01 && chunk_zero && WB_SEL_BITS <= 16;
        decode_q[2] <= opcode == 8'h02 && chunk_zero;
        decode_q[3] <= opcode == 8'h03;
        decode_q[4] <= opcode == 8'h04;
        decode_q[5] <= opcode == 8'h05;
        decode_q[6] <= opcode == 8'h06;
        decode_q[7] <= opcode == 8'h07;
        decode_q[8] <= opcode == 8'h08;
        decode_q[9] <= opcode == 8'h09;
        decode_q[10] <= opcode == 8'h0a;
        decode_q[11] <= opcode == 8'h0b;
        decode_q[12] <= opcode == 8'h0c && chunk_zero;
        decode_q[13] <= opcode == 8'h0d && chunk_zero && WB_SEL_BITS <= 16;
        decode_q[14] <= opcode == 8'h0e && chunk_zero && WB_SEL_BITS <= 16;
        decode_q[15] <= opcode == 8'h0f && chunk_zero && WB_SEL_BITS <= 16;
        decode_q[16] <= opcode == 8'h10 && chunk_zero && WB_SEL_BITS <= 16;
        decode_q[17] <= opcode == 8'h11 && chunk_zero && WB_SEL_BITS == 8;
        decode_q[18] <= opcode == 8'h12 && chunk_zero;
        decode_q[19] <= opcode == 8'h13 && chunk_zero;
      end
    end
  end
endmodule
`default_nettype wire
