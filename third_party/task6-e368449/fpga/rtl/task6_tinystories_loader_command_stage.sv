`timescale 1ns/1ps
`default_nettype none

// Registers the host command boundary and emits operation-specific one-cycle
// dispatch pulses.  The wide loader decoder never depends directly on the
// physical command-event net.
module task6_tinystories_loader_command_stage #(
  parameter int COMMAND_WIDTH = 208,
  parameter logic [31:0] COMMAND_MAGIC = 32'h33445244
) (
  input  wire                     clk,
  input  wire                     rst,
  input  wire                     capture_enable,
  input  wire                     command_event,
  input  wire [COMMAND_WIDTH-1:0] command_payload,
  output logic [COMMAND_WIDTH-1:0] staged_payload,
  output logic                    dispatch_read_dense,
  output logic                    dispatch_load_beat,
  output logic                    dispatch_run_packet,
  output logic                    dispatch_load_pair,
  output logic                    dispatch_invalid,
  output wire                     dispatch_any
);
  wire [31:0] command_magic = command_payload[0 +: 32];
  wire [7:0] command_opcode = command_payload[32 +: 8];
  wire [1:0] command_chunk = command_payload[40 +: 2];

  assign dispatch_any = dispatch_read_dense || dispatch_load_beat ||
    dispatch_run_packet || dispatch_load_pair || dispatch_invalid;

  always_ff @(posedge clk) begin
    if (rst) begin
      staged_payload <= '0;
      dispatch_read_dense <= 1'b0;
      dispatch_load_beat <= 1'b0;
      dispatch_run_packet <= 1'b0;
      dispatch_load_pair <= 1'b0;
      dispatch_invalid <= 1'b0;
    end else begin
      dispatch_read_dense <= 1'b0;
      dispatch_load_beat <= 1'b0;
      dispatch_run_packet <= 1'b0;
      dispatch_load_pair <= 1'b0;
      dispatch_invalid <= 1'b0;

      if (capture_enable && command_event) begin
        staged_payload <= command_payload;
        if (command_magic != COMMAND_MAGIC || command_chunk != 2'd0) begin
          dispatch_invalid <= 1'b1;
        end else begin
          case (command_opcode)
            8'h06: dispatch_read_dense <= 1'b1;
            8'h0f: dispatch_load_beat <= 1'b1;
            8'h10: dispatch_run_packet <= 1'b1;
            8'h11: dispatch_load_pair <= 1'b1;
            default: dispatch_invalid <= 1'b1;
          endcase
        end
      end
    end
  end
endmodule

`default_nettype wire
