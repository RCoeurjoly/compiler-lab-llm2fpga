`default_nettype none

// Single-outstanding arbiter between compiler-generated logical memories and
// the validated 128-bit UberDDR3 Wishbone port. Requests are byte addresses;
// responses are routed to the requester's 64-bit lane. The generated memory
// cells hold their request until the one-cycle response pulse arrives.
module llm_external_memory_arbiter #(
  parameter int PORTS = 2,
  parameter int ADDRESS_BITS = 32,
  parameter int DATA_BITS = 64,
  parameter int WB_DATA_BITS = 128
) (
  input  logic clk,
  input  logic rst,
  input  logic [PORTS-1:0] req_valid,
  output logic [PORTS-1:0] req_ready,
  input  logic [PORTS*ADDRESS_BITS-1:0] req_addr,
  output logic [PORTS-1:0] rsp_valid,
  output logic [PORTS*DATA_BITS-1:0] rsp_data,
  output logic wb_cyc,
  output logic wb_stb,
  output logic [ADDRESS_BITS-1:0] wb_addr,
  output logic [WB_DATA_BITS/8-1:0] wb_sel,
  input logic wb_accept,
  input logic wb_ack,
  input logic wb_err,
  input logic [WB_DATA_BITS-1:0] wb_rdata
);
  localparam int BYTE_LANES = WB_DATA_BITS / 8;
  localparam int LANE_BITS = $clog2(BYTE_LANES);
  typedef enum logic [1:0] {IDLE, ISSUE, WAIT_ACK} state_t;
  state_t state;
  logic [$clog2(PORTS)-1:0] owner;
  logic [ADDRESS_BITS-1:0] saved_addr;
  always_comb begin
    req_ready = '0;
    rsp_valid = '0;
    rsp_data = '0;
    wb_cyc = state != IDLE;
    wb_stb = state == ISSUE;
    wb_addr = saved_addr >> LANE_BITS;
    wb_sel = '1;
    if (state == IDLE) begin
      for (int i = 0; i < PORTS; i = i + 1)
        if (req_valid[i] && req_ready == '0)
          req_ready[i] = 1'b1;
    end
    if (state == WAIT_ACK && (wb_ack || wb_err)) begin
      rsp_valid[owner] = 1'b1;
      if (saved_addr[LANE_BITS-1:0] < BYTE_LANES/2)
        rsp_data[owner*DATA_BITS +: DATA_BITS] = wb_rdata[DATA_BITS-1:0];
      else
        rsp_data[owner*DATA_BITS +: DATA_BITS] = wb_rdata[WB_DATA_BITS-1 -: DATA_BITS];
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state <= IDLE;
      owner <= '0;
      saved_addr <= '0;
    end else begin
      case (state)
        IDLE: begin
          for (int i = 0; i < PORTS; i = i + 1)
            if (req_valid[i] && req_ready[i]) begin
              owner <= i;
              saved_addr <= req_addr[i*ADDRESS_BITS +: ADDRESS_BITS];
              state <= ISSUE;
            end
        end
        ISSUE: if (wb_accept) state <= WAIT_ACK;
        WAIT_ACK: if (wb_ack || wb_err) state <= IDLE;
        default: state <= IDLE;
      endcase
    end
  end
endmodule

`default_nettype wire
