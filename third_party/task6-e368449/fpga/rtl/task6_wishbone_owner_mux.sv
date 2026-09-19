`timescale 1ns/1ps
`default_nettype none

module task6_wishbone_owner_mux #(
  parameter int ADDR_BITS = 25,
  parameter int DATA_BITS = 512,
  parameter bit DIRECT_ACCELERATOR_OWNER = 1'b0
) (
  input  wire                   clk,
  input  wire                   rst,
  input  wire                   accelerator_enable,

  input  wire                   host_cyc,
  input  wire                   host_stb,
  input  wire                   host_we,
  input  wire [ADDR_BITS-1:0]   host_addr,
  input  wire [DATA_BITS-1:0]   host_write_data,
  input  wire [DATA_BITS/8-1:0] host_sel,
  output wire                   host_stall,
  output wire                   host_ack,
  output wire                   host_err,
  output wire [DATA_BITS-1:0]   host_read_data,

  input  wire                   accelerator_cyc,
  input  wire                   accelerator_stb,
  input  wire                   accelerator_we,
  input  wire [ADDR_BITS-1:0]   accelerator_addr,
  input  wire [DATA_BITS-1:0]   accelerator_write_data,
  input  wire [DATA_BITS/8-1:0] accelerator_sel,
  output wire                   accelerator_stall,
  output wire                   accelerator_ack,
  output wire                   accelerator_err,
  output wire [DATA_BITS-1:0]   accelerator_read_data,

  output wire                   memory_cyc,
  output wire                   memory_stb,
  output wire                   memory_we,
  output wire [ADDR_BITS-1:0]   memory_addr,
  output wire [DATA_BITS-1:0]   memory_write_data,
  output wire [DATA_BITS/8-1:0] memory_sel,
  input  wire                   memory_stall,
  input  wire                   memory_ack,
  input  wire                   memory_err,
  input  wire [DATA_BITS-1:0]   memory_read_data,

  output wire                   owner_active,
  output wire                   accelerator_owned
);
  logic owner_active_q;
  logic accelerator_owned_q;

  // TinyStories latches ownership at inference start.  In that mode the
  // arbitration state is unnecessary: host traffic is selected before start,
  // and accelerator traffic is selected for the entire inference thereafter.
  wire select_accelerator = DIRECT_ACCELERATOR_OWNER
    ? accelerator_enable
    : (owner_active_q ? accelerator_owned_q : accelerator_enable && accelerator_cyc);
  wire select_host = DIRECT_ACCELERATOR_OWNER
    ? !accelerator_enable && host_cyc
    : (owner_active_q ? !accelerator_owned_q : !select_accelerator && host_cyc);

  always_ff @(posedge clk) begin
    if (rst) begin
      owner_active_q <= 1'b0;
      accelerator_owned_q <= 1'b0;
    end else if (owner_active_q) begin
      if ((accelerator_owned_q && !accelerator_cyc) ||
          (!accelerator_owned_q && !host_cyc)) begin
        owner_active_q <= 1'b0;
        accelerator_owned_q <= 1'b0;
      end
    end else if (accelerator_enable && accelerator_cyc) begin
      owner_active_q <= 1'b1;
      accelerator_owned_q <= 1'b1;
    end else if (host_cyc) begin
      owner_active_q <= 1'b1;
      accelerator_owned_q <= 1'b0;
    end
  end

  assign memory_cyc = select_accelerator ? accelerator_cyc :
                      select_host ? host_cyc : 1'b0;
  assign memory_stb = select_accelerator ? accelerator_stb :
                      select_host ? host_stb : 1'b0;
  assign memory_we = select_accelerator ? accelerator_we :
                     select_host ? host_we : 1'b0;
  assign memory_addr = select_accelerator ? accelerator_addr : host_addr;
  assign memory_write_data = select_accelerator ? accelerator_write_data :
                             host_write_data;
  assign memory_sel = select_accelerator ? accelerator_sel : host_sel;

  assign host_stall = select_host ? memory_stall : host_cyc;
  assign host_ack = select_host && memory_ack;
  assign host_err = select_host && memory_err;
  assign host_read_data = select_host ? memory_read_data : '0;
  assign accelerator_read_data = select_accelerator ? memory_read_data : '0;

  assign accelerator_stall = select_accelerator ? memory_stall : accelerator_cyc;
  assign accelerator_ack = select_accelerator && memory_ack;
  assign accelerator_err = select_accelerator && memory_err;

  assign owner_active = owner_active_q;
  assign accelerator_owned = owner_active_q && accelerator_owned_q;
endmodule

`default_nettype wire
