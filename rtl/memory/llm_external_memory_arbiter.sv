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
  localparam int OWNER_BITS = (PORTS > 1) ? $clog2(PORTS) : 1;
  localparam int PRIORITY_GROUP_WIDTH = 16;
  localparam int PRIORITY_GROUPS =
    (PORTS + PRIORITY_GROUP_WIDTH - 1) / PRIORITY_GROUP_WIDTH;
  localparam int LOCAL_BITS = $clog2(PRIORITY_GROUP_WIDTH);
  localparam int GROUP_BITS = (PRIORITY_GROUPS > 1) ? $clog2(PRIORITY_GROUPS) : 1;
  typedef enum logic [1:0] {IDLE, CAPTURE, ISSUE, WAIT_ACK} state_t;
  state_t state;
  logic [OWNER_BITS-1:0] owner;
  logic [GROUP_BITS-1:0] last_grant_group;
  logic [PRIORITY_GROUPS*LOCAL_BITS-1:0] last_grant_local;
  logic [ADDRESS_BITS-1:0] saved_addr;
  logic [PORTS-1:0] grant;
  logic [OWNER_BITS-1:0] grant_owner;
  logic [ADDRESS_BITS-1:0] grant_addr;
  logic [PORTS-1:0] selected_grant_q;
  logic [OWNER_BITS-1:0] selected_owner_q;
  logic response_valid_q;
  logic [OWNER_BITS-1:0] response_owner_q;
  logic [DATA_BITS-1:0] response_data_q;
  logic [PRIORITY_GROUPS*PRIORITY_GROUP_WIDTH-1:0] padded_req_valid;
  logic [PRIORITY_GROUPS-1:0] group_valid;
  logic [GROUP_BITS-1:0] group_start;
  logic [PRIORITY_GROUPS-1:0] group_priority_mask;
  logic [PRIORITY_GROUPS-1:0] group_after_last;
  logic [PRIORITY_GROUPS-1:0] group_candidates;
  logic [PRIORITY_GROUPS-1:0] group_grant;
  logic [PRIORITY_GROUPS*PRIORITY_GROUP_WIDTH-1:0] local_grant;
  logic [PRIORITY_GROUPS*PRIORITY_GROUP_WIDTH-1:0] padded_grant;
  logic [LOCAL_BITS-1:0] local_start;
  logic [PRIORITY_GROUP_WIDTH-1:0] local_mask;
  logic [PRIORITY_GROUP_WIDTH-1:0] local_after_last;
  logic [PRIORITY_GROUP_WIDTH-1:0] local_candidates;
  always_comb begin
    req_ready = '0;
    rsp_valid = '0;
    // The read word is registered when Wishbone completes and then broadcast
    // to all ports; rsp_valid identifies the sole consumer.  This avoids a
    // saved-address lane mux followed by a 240-way data demultiplexer and the
    // per-memory byte extractor in one same-cycle critical path.
    rsp_data = {PORTS{response_data_q}};
    // Round-robin among 16-requester groups and within each group. Persistent
    // level-held requests otherwise let a low-index memory starve later banks
    // while it reissues the same read waiting for the other banks to finish.
    padded_req_valid = '0;
    padded_req_valid[PORTS-1:0] = req_valid;
    group_valid = '0;
    group_start = last_grant_group + 1'b1;
    if (group_start >= GROUP_BITS'(PRIORITY_GROUPS)) group_start = '0;
    group_priority_mask = {PRIORITY_GROUPS{1'b1}} << group_start;
    group_after_last = '0;
    group_candidates = '0;
    local_grant = '0;
    for (int g = 0; g < PRIORITY_GROUPS; g = g + 1) begin
      group_valid[g] = |padded_req_valid[g*PRIORITY_GROUP_WIDTH +: PRIORITY_GROUP_WIDTH];
      local_start = last_grant_local[g*LOCAL_BITS +: LOCAL_BITS] + 1'b1;
      local_mask = {PRIORITY_GROUP_WIDTH{1'b1}} << local_start;
      local_after_last =
        padded_req_valid[g*PRIORITY_GROUP_WIDTH +: PRIORITY_GROUP_WIDTH] & local_mask;
      local_candidates = (|local_after_last) ? local_after_last :
        padded_req_valid[g*PRIORITY_GROUP_WIDTH +: PRIORITY_GROUP_WIDTH];
      local_grant[g*PRIORITY_GROUP_WIDTH +: PRIORITY_GROUP_WIDTH] =
        local_candidates & (~local_candidates + {{(PRIORITY_GROUP_WIDTH-1){1'b0}}, 1'b1});
    end
    group_after_last = group_valid & group_priority_mask;
    group_candidates = (|group_after_last) ? group_after_last : group_valid;
    group_grant = group_candidates &
      (~group_candidates + {{(PRIORITY_GROUPS-1){1'b0}}, 1'b1});
    padded_grant = '0;
    for (int g = 0; g < PRIORITY_GROUPS; g = g + 1)
      padded_grant[g*PRIORITY_GROUP_WIDTH +: PRIORITY_GROUP_WIDTH] =
        local_grant[g*PRIORITY_GROUP_WIDTH +: PRIORITY_GROUP_WIDTH] &
        {PRIORITY_GROUP_WIDTH{group_grant[g]}};
    grant = padded_grant[PORTS-1:0];
    grant_owner = '0;
    grant_addr = '0;
    for (int i = 0; i < PORTS; i = i + 1) begin
      grant_owner |= OWNER_BITS'(i) & {OWNER_BITS{grant[i]}};
      // Selection is registered before this payload mux. The requester has
      // not received ready yet, so it must still hold its valid and address.
      grant_addr |= req_addr[i*ADDRESS_BITS +: ADDRESS_BITS] &
        {ADDRESS_BITS{selected_grant_q[i]}};
    end
    wb_cyc = (state == ISSUE) || (state == WAIT_ACK);
    wb_stb = state == ISSUE;
    wb_addr = saved_addr >> LANE_BITS;
    wb_sel = '1;
    if (state == CAPTURE && !rst) req_ready = selected_grant_q & req_valid;
    for (int i = 0; i < PORTS; i = i + 1)
      rsp_valid[i] = response_valid_q && (response_owner_q == OWNER_BITS'(i));
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state <= IDLE;
      owner <= '0;
      last_grant_group <= GROUP_BITS'(PRIORITY_GROUPS - 1);
      last_grant_local <= '1;
      saved_addr <= '0;
      selected_grant_q <= '0;
      selected_owner_q <= '0;
      response_valid_q <= 1'b0;
      response_owner_q <= '0;
      response_data_q <= '0;
    end else begin
      response_valid_q <= 1'b0;
      response_data_q <= '0;
      case (state)
        IDLE: if (|grant) begin
          selected_grant_q <= grant;
          selected_owner_q <= grant_owner;
          state <= CAPTURE;
        end
        CAPTURE: if (|req_ready) begin
          owner <= selected_owner_q;
          saved_addr <= grant_addr;
          for (int g = 0; g < PRIORITY_GROUPS; g = g + 1) begin
            if (selected_owner_q / PRIORITY_GROUP_WIDTH == g) begin
              last_grant_group <= GROUP_BITS'(g);
              last_grant_local[g*LOCAL_BITS +: LOCAL_BITS] <= LOCAL_BITS'(selected_owner_q);
            end
          end
          state <= ISSUE;
        end else begin
          // A withdrawn choice must not issue a read or advance fairness.
          // Compiler memory clients normally hold valid until acceptance.
          state <= IDLE;
        end
        ISSUE: if (wb_accept) state <= WAIT_ACK;
        WAIT_ACK: if (wb_ack || wb_err) begin
          response_owner_q <= owner;
          if (saved_addr[LANE_BITS-1:0] < BYTE_LANES/2)
            response_data_q <= wb_rdata[DATA_BITS-1:0];
          else
            response_data_q <= wb_rdata[WB_DATA_BITS-1 -: DATA_BITS];
          response_valid_q <= 1'b1;
          state <= IDLE;
        end
        default: state <= IDLE;
      endcase
    end
  end
endmodule

`default_nettype wire
