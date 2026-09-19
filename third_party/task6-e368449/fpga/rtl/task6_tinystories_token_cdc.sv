`timescale 1ns/1ps
`default_nettype none

module task6_tinystories_token_cdc (
  input  wire         rowstream_clk,
  input  wire         rowstream_rst_n,
  input  wire         pcie_clk,
  input  wire         pcie_rst_n,
  input  wire         pcie_start,
  input  wire         pcie_clear,
  input  wire         rowstream_token_valid,
  output wire         rowstream_token_ready,
  input  wire [15:0]  rowstream_token_id,
  output wire [5:0]   pcie_token_count,
  output wire [511:0] pcie_tokens,
  output wire         pcie_overflow
);
  reg [2:0] pcie_reset_release_sync_row_q;
  reg [2:0] acknowledge_sync_row_q;
  reg [2:0] epoch_sync_row_q;
  reg epoch_seen_row_q;
  reg rowstream_armed_q;
  reg request_toggle_row_q;
  reg [15:0] token_hold_row_q;
  reg token_epoch_hold_row_q;

  reg [2:0] request_sync_pcie_q;
  reg request_seen_pcie_q;
  reg acknowledge_toggle_pcie_q;
  reg epoch_pcie_q;
  reg pcie_token_valid_q;
  reg [15:0] pcie_token_id_q;

  wire pcie_epoch_advance = pcie_start || pcie_clear;
  wire rowstream_bridge_rst_n = rowstream_rst_n &&
      pcie_reset_release_sync_row_q[2];
  wire rowstream_in_flight = request_toggle_row_q !=
      acknowledge_sync_row_q[2];
  wire request_event_pcie = request_sync_pcie_q[2] !=
      request_seen_pcie_q;
  wire token_for_current_epoch = token_epoch_hold_row_q == epoch_pcie_q;

  assign rowstream_token_ready = rowstream_armed_q && !rowstream_in_flight;

  // PCIe reset is asynchronous to rowstream_clk. Assert its row-domain
  // effect immediately, but release only after three rowstream clock edges.
  always_ff @(posedge rowstream_clk or negedge pcie_rst_n) begin
    if (!pcie_rst_n)
      pcie_reset_release_sync_row_q <= 3'b000;
    else
      pcie_reset_release_sync_row_q <= {
        pcie_reset_release_sync_row_q[1:0], 1'b1
      };
  end

  always_ff @(posedge rowstream_clk or negedge rowstream_bridge_rst_n) begin
    if (!rowstream_bridge_rst_n) begin
      acknowledge_sync_row_q <= 3'b000;
      epoch_sync_row_q <= 3'b000;
      epoch_seen_row_q <= 1'b0;
      rowstream_armed_q <= 1'b0;
      request_toggle_row_q <= 1'b0;
      token_hold_row_q <= 16'd0;
      token_epoch_hold_row_q <= 1'b0;
    end else begin
      acknowledge_sync_row_q <= {
        acknowledge_sync_row_q[1:0], acknowledge_toggle_pcie_q
      };
      epoch_sync_row_q <= {epoch_sync_row_q[1:0], epoch_pcie_q};

      if (epoch_sync_row_q[2] != epoch_seen_row_q) begin
        epoch_seen_row_q <= epoch_sync_row_q[2];
        rowstream_armed_q <= 1'b1;
      end

      if (rowstream_token_valid && rowstream_token_ready) begin
        token_hold_row_q <= rowstream_token_id;
        token_epoch_hold_row_q <= epoch_sync_row_q[2];
        request_toggle_row_q <= ~request_toggle_row_q;
      end
    end
  end

  always_ff @(posedge pcie_clk) begin
    if (!pcie_rst_n) begin
      request_sync_pcie_q <= 3'b000;
      request_seen_pcie_q <= 1'b0;
      acknowledge_toggle_pcie_q <= 1'b0;
      epoch_pcie_q <= 1'b0;
      pcie_token_valid_q <= 1'b0;
      pcie_token_id_q <= 16'd0;
    end else begin
      request_sync_pcie_q <= {
        request_sync_pcie_q[1:0], request_toggle_row_q
      };
      pcie_token_valid_q <= 1'b0;

      if (pcie_epoch_advance)
        epoch_pcie_q <= ~epoch_pcie_q;

      if (request_event_pcie) begin
        request_seen_pcie_q <= request_sync_pcie_q[2];
        acknowledge_toggle_pcie_q <= request_sync_pcie_q[2];
        pcie_token_valid_q <= token_for_current_epoch &&
            !pcie_epoch_advance;
        pcie_token_id_q <= token_hold_row_q;
      end
    end
  end

  task6_tinystories_token_collector collector (
    .clk(pcie_clk),
    .rst(!pcie_rst_n),
    .clear(pcie_epoch_advance),
    .start(1'b0),
    .token_valid(pcie_token_valid_q),
    .token_ready(),
    .token_id(pcie_token_id_q),
    .token_count(pcie_token_count),
    .tokens(pcie_tokens),
    .overflow(pcie_overflow)
  );
endmodule

`default_nettype wire
