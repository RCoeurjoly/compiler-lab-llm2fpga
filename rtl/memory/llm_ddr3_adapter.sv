`timescale 1ns/1ps

// Single-outstanding adapter from the compiler logical INT8 memory contract to
// the audited 128-bit UberDDR3 user port.  The external port returns a whole
// 16-byte line; the requested byte is selected without changing its value.
// Prefetch is represented by the line-aligned request policy and is deliberately
// kept outside the accelerator arithmetic.
module llm_ddr3_adapter #(
  parameter int ADDRESS_WIDTH = 32,
  parameter int DDR_DATA_WIDTH = 128
) (
  input logic clk, input logic rst,
  input logic read_valid,
  input logic [ADDRESS_WIDTH-1:0] read_address,
  output logic response_valid,
  output logic [ADDRESS_WIDTH-1:0] response_address,
  output logic [7:0] response_data,
  output logic response_error,
  output logic wb_cyc, output logic wb_stb, output logic wb_we,
  output logic [ADDRESS_WIDTH-1:0] wb_addr,
  output logic [DDR_DATA_WIDTH/8-1:0] wb_sel,
  input logic wb_accept, input logic wb_ack, input logic wb_err,
  input logic [DDR_DATA_WIDTH-1:0] wb_rdata
);
  localparam int DDR_BYTES = DDR_DATA_WIDTH / 8;
  localparam int LANE_BITS = $clog2(DDR_BYTES);
  typedef enum logic [1:0] {IDLE, WAIT_ACCEPT, WAIT_ACK} state_t;
  state_t state;
  logic [ADDRESS_WIDTH-1:0] saved_address;
  logic [LANE_BITS-1:0] saved_lane;

  initial if (DDR_DATA_WIDTH != 128)
    $error("llm_ddr3_adapter requires the validated 128-bit DDR3 port");

  always_comb begin
    wb_cyc = state == WAIT_ACCEPT;
    wb_stb = state == WAIT_ACCEPT;
    wb_we = 1'b0;
    // UberDDR3 addresses 16-byte Wishbone words.
    wb_addr = saved_address >> LANE_BITS;
    wb_sel = ({{(DDR_BYTES-1){1'b0}}, 1'b1} << saved_lane);
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state <= IDLE;
      saved_address <= '0;
      saved_lane <= '0;
      response_valid <= 1'b0;
      response_address <= '0;
      response_data <= '0;
      response_error <= 1'b0;
    end else begin
      response_valid <= 1'b0;
      case (state)
        IDLE: if (read_valid) begin
          saved_address <= read_address;
          saved_lane <= read_address[LANE_BITS-1:0];
          state <= WAIT_ACCEPT;
        end
        WAIT_ACCEPT: if (wb_accept) state <= WAIT_ACK;
        WAIT_ACK: if (wb_ack) begin
          response_valid <= 1'b1;
          response_address <= saved_address;
          response_data <= wb_rdata[saved_lane*8 +: 8];
          response_error <= wb_err;
          state <= IDLE;
        end
        default: state <= IDLE;
      endcase
    end
  end
endmodule
