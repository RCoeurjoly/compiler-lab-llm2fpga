`timescale 1ns/1ps

// Read-only, single-outstanding RC-memory to UberDDR3 user-port adapter.
//
// req_byte_address is a logical byte address from the authenticated mapping.
// wb_addr is consequently a 16-byte Wishbone word address; lane zero holds
// the lowest-address byte of wb_rdata.
module rc_ddr3_adapter #(
  parameter int ADDRESS_WIDTH = 32,
  parameter int CLIENT_DATA_WIDTH = 32,
  parameter int DDR_DATA_WIDTH = 128
) (
  input  logic                         clk,
  input  logic                         rst,

  input  logic                         req_valid,
  input  logic                         req_write,
  input  logic [ADDRESS_WIDTH-1:0]     req_byte_address,
  output logic                         resp_valid,
  output logic                         resp_error,
  output logic [CLIENT_DATA_WIDTH-1:0] resp_rdata,

  output logic                         wb_cyc,
  output logic                         wb_stb,
  output logic                         wb_we,
  output logic [ADDRESS_WIDTH-1:0]     wb_addr,
  output logic [DDR_DATA_WIDTH/8-1:0]  wb_sel,
  input  logic                         wb_accept,
  input  logic                         wb_ack,
  input  logic                         wb_err,
  input  logic [DDR_DATA_WIDTH-1:0]    wb_rdata
);
  localparam int DDR_BYTES = DDR_DATA_WIDTH / 8;
  localparam int CLIENT_BYTES = CLIENT_DATA_WIDTH / 8;
  localparam int DDR_BYTE_SHIFT = $clog2(DDR_BYTES);
  localparam logic [DDR_BYTES-1:0] CLIENT_MASK =
      ({DDR_BYTES{1'b1}} >> (DDR_BYTES - CLIENT_BYTES));

  typedef enum logic [1:0] {IDLE, WAIT_ACCEPT, WAIT_ACK} state_t;
  state_t state;
  logic [ADDRESS_WIDTH-1:0] saved_byte_address;
  logic [DDR_BYTE_SHIFT-1:0] saved_lane;
  int unsigned lane_offset;

  always_comb lane_offset = {{(32 - DDR_BYTE_SHIFT){1'b0}},
                             req_byte_address[DDR_BYTE_SHIFT-1:0]};

  initial begin
    if (DDR_DATA_WIDTH != 128 || DDR_BYTES != 16 || CLIENT_DATA_WIDTH % 8 != 0
        || CLIENT_BYTES == 0 || CLIENT_BYTES > DDR_BYTES)
      $error("rc_ddr3_adapter only implements the audited 128-bit, 16-byte transport");
  end

  always_comb begin
    wb_cyc = state == WAIT_ACCEPT;
    wb_stb = state == WAIT_ACCEPT;
    wb_we = 1'b0;
    wb_addr = saved_byte_address >> DDR_BYTE_SHIFT;
    wb_sel = CLIENT_MASK << saved_lane;
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state <= IDLE;
      saved_byte_address <= '0;
      saved_lane <= '0;
      resp_valid <= 1'b0;
      resp_error <= 1'b0;
      resp_rdata <= '0;
    end else begin
      resp_valid <= 1'b0;
      case (state)
        IDLE: begin
          if (req_valid) begin
            if (req_write || lane_offset > DDR_BYTES - CLIENT_BYTES) begin
              resp_valid <= 1'b1;
              resp_error <= 1'b1;
              resp_rdata <= '0;
            end else begin
              saved_byte_address <= req_byte_address;
              saved_lane <= req_byte_address[DDR_BYTE_SHIFT-1:0];
              state <= WAIT_ACCEPT;
            end
          end
        end
        WAIT_ACCEPT: begin
          if (wb_accept)
            state <= WAIT_ACK;
        end
        WAIT_ACK: begin
          if (wb_ack) begin
            resp_valid <= 1'b1;
            resp_error <= wb_err;
            resp_rdata <= wb_rdata[saved_lane * 8 +: CLIENT_DATA_WIDTH];
            state <= IDLE;
          end
        end
        default: state <= IDLE;
      endcase
    end
  end
endmodule
