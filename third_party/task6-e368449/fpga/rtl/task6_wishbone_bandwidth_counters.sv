`timescale 1ns/1ps
`default_nettype none

module task6_wishbone_bandwidth_counters #(
  parameter int SEL_BITS = 8
) (
  input  wire                  clk_i,
  input  wire                  rst_ni,
  input  wire                  clear_i,
  input  wire                  cyc_i,
  input  wire                  stb_i,
  input  wire                  we_i,
  input  wire [SEL_BITS - 1:0] sel_i,
  input  wire                  ack_i,
  output logic [63:0]          read_bytes_o,
  output logic [63:0]          write_bytes_o,
  output logic [63:0]          active_cycles_o,
  output logic [63:0]          stall_cycles_o
);
  logic [63:0] selected_bytes;
  logic [63:0] pending_selected_bytes;
  logic pending_q;
  logic pending_we_q;
  logic [SEL_BITS - 1:0] pending_sel_q;

  always_comb begin
    selected_bytes = 64'd0;
    pending_selected_bytes = 64'd0;
    for (int lane = 0; lane < SEL_BITS; lane = lane + 1)
      selected_bytes = selected_bytes + {{63{1'b0}}, sel_i[lane]};
    for (int lane = 0; lane < SEL_BITS; lane = lane + 1)
      pending_selected_bytes = pending_selected_bytes + {{63{1'b0}}, pending_sel_q[lane]};
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      read_bytes_o <= 64'd0;
      write_bytes_o <= 64'd0;
      active_cycles_o <= 64'd0;
      stall_cycles_o <= 64'd0;
      pending_q <= 1'b0;
      pending_we_q <= 1'b0;
      pending_sel_q <= '0;
    end else if (clear_i) begin
      read_bytes_o <= 64'd0;
      write_bytes_o <= 64'd0;
      active_cycles_o <= 64'd0;
      stall_cycles_o <= 64'd0;
      pending_q <= 1'b0;
      pending_we_q <= 1'b0;
      pending_sel_q <= '0;
    end else begin
      if (!pending_q && cyc_i && stb_i) begin
        active_cycles_o <= active_cycles_o + 64'd1;
        if (ack_i) begin
          if (we_i)
            write_bytes_o <= write_bytes_o + selected_bytes;
          else
            read_bytes_o <= read_bytes_o + selected_bytes;
        end else begin
          stall_cycles_o <= stall_cycles_o + 64'd1;
          pending_q <= 1'b1;
          pending_we_q <= we_i;
          pending_sel_q <= sel_i;
        end
      end else if (pending_q) begin
        active_cycles_o <= active_cycles_o + 64'd1;
        if (ack_i) begin
          pending_q <= 1'b0;
          if (pending_we_q)
            write_bytes_o <= write_bytes_o + pending_selected_bytes;
          else
            read_bytes_o <= read_bytes_o + pending_selected_bytes;
        end else begin
          stall_cycles_o <= stall_cycles_o + 64'd1;
        end
      end
    end
  end
endmodule

`default_nettype wire
