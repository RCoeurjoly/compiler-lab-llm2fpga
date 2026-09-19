`timescale 1ns/1ps
`default_nettype none
// TEMPORARY DIAGNOSTIC ONLY: dedicated versioned AXI-Lite sub-window.
// Follows task6 ingress semantics: independent AW/W holding registers, one
// write execution, BVALID/RVALID retained until the consumer acknowledges.
// Existing task6 loader registers are not implemented or aliased here.
module compiler_ddr3_trace_replay_csr (
    input wire clk, reset, transport_reset, replay_reset, calib_complete,
    input wire [31:0] s_axi_awaddr,
    input wire s_axi_awvalid,
    output wire s_axi_awready,
    input wire [31:0] s_axi_wdata,
    input wire [3:0] s_axi_wstrb,
    input wire s_axi_wvalid,
    output wire s_axi_wready,
    output reg [1:0] s_axi_bresp,
    output reg s_axi_bvalid,
    input wire s_axi_bready,
    input wire [31:0] s_axi_araddr,
    input wire s_axi_arvalid,
    output wire s_axi_arready,
    output reg [31:0] s_axi_rdata,
    output reg s_axi_rvalid,
    input wire s_axi_rready,
    output reg [1:0] s_axi_rresp,
    output wire replay_active,
    output wire wb_cyc, wb_stb, wb_we,
    output wire [31:0] wb_addr,
    output wire [15:0] wb_sel,
    input wire wb_stall, wb_ack, wb_err,
    input wire [127:0] wb_rdata
);
  reg aw_pending, w_pending;
  reg [31:0] awaddr, wdata;
  reg [3:0] wstrb;
  reg [31:0] staged_address;
  reg [127:0] staged_expected;
  reg [4:0] staged_mask;
  wire [1:0] state;
  assign replay_active = state == 1;
  wire sealed, starved, push_ready;
  wire [4:0] fifo_level;
  wire [31:0] expected_count, pushed_count, accepted_count, response_count, checked_count;
  wire [31:0] error_bits, first_index, first_address;
  wire [127:0] first_expected, first_actual;
  wire in_window = awaddr>=32'h900 && awaddr<32'h980;
  wire aligned = awaddr[1:0]==0;
  wire is_push = awaddr==32'h924;
  wire is_command = awaddr==32'h908;
  wire is_stage = awaddr>=32'h910 && awaddr<=32'h920;
  wire writable = is_command || awaddr==32'h90c || is_stage || is_push;
  wire malformed = !aligned || wstrb!=4'hf || !writable ||
       (is_push && (wdata!=1 || staged_mask!=5'b11111)) ||
       (is_command && wdata!=1 && wdata!=2 && wdata!=4);
  // Only a valid PUSH waits for space. Invalid/extra/terminal writes always
  // finish, letting the host observe failure rather than deadlocking AXI.
  wire full_wait = is_push && !malformed && fifo_level==16 &&
                  (state==0 || state==1) && !sealed && pushed_count<expected_count;
  wire execute = !transport_reset && aw_pending && w_pending && !s_axi_bvalid && !full_wait;
  wire valid_write = execute && in_window && !malformed;
  wire clear = valid_write && is_command && wdata==2;
  assign s_axi_awready = !reset && !transport_reset && !aw_pending && !s_axi_bvalid;
  assign s_axi_wready = !reset && !transport_reset && !w_pending && !s_axi_bvalid;
  assign s_axi_arready = !reset && !transport_reset && !s_axi_rvalid;

  compiler_ddr3_trace_replay replay (
    .clk(clk), .reset(reset), .replay_reset(replay_reset), .calib_complete(calib_complete),
    .clear(clear), .start(valid_write && is_command && wdata==1),
    .finish(valid_write && is_command && wdata==4),
    .configure(valid_write && awaddr==32'h90c), .configured_count(wdata),
    .protocol_error(execute && in_window && malformed),
    .push(valid_write && is_push), .push_address(staged_address), .push_expected(staged_expected),
    .push_ready(push_ready), .state(state), .sealed(sealed), .starved(starved),
    .fifo_level(fifo_level), .expected_count(expected_count), .pushed_count(pushed_count),
    .accepted_count(accepted_count), .response_count(response_count), .checked_count(checked_count),
    .error_bits(error_bits), .first_index(first_index), .first_address(first_address),
    .first_expected(first_expected), .first_actual(first_actual),
    .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_we(wb_we), .wb_addr(wb_addr), .wb_sel(wb_sel),
    .wb_stall(wb_stall), .wb_ack(wb_ack), .wb_err(wb_err), .wb_rdata(wb_rdata)
  );

  reg [31:0] read_value;
  reg read_invalid;
  always @* begin
    read_value=0; read_invalid=0;
    case(s_axi_araddr)
      32'h900: read_value=32'h52504c59;
      32'h904: read_value=1;
      32'h90c: read_value=expected_count;
      32'h928: read_value={30'd0,state};
      32'h92c: read_value={28'd0,starved,sealed,push_ready,calib_complete};
      32'h930: read_value={27'd0,fifo_level};
      32'h934: read_value=pushed_count;
      32'h938: read_value=accepted_count;
      32'h93c: read_value=response_count;
      32'h940: read_value=checked_count;
      32'h944: read_value=error_bits;
      32'h948: read_value=first_index;
      32'h94c: read_value=first_address;
      32'h950: read_value=first_expected[31:0];
      32'h954: read_value=first_expected[63:32];
      32'h958: read_value=first_expected[95:64];
      32'h95c: read_value=first_expected[127:96];
      32'h960: read_value=first_actual[31:0];
      32'h964: read_value=first_actual[63:32];
      32'h968: read_value=first_actual[95:64];
      32'h96c: read_value=first_actual[127:96];
      32'h970: read_value={27'd0,staged_mask};
      default: read_invalid=1;
    endcase
  end

  always @(posedge clk) begin
    if (reset) begin
      aw_pending<=0; w_pending<=0; awaddr<=0; wdata<=0; wstrb<=0;
      s_axi_bvalid<=0; s_axi_bresp<=0; s_axi_rvalid<=0; s_axi_rresp<=0; s_axi_rdata<=0;
      staged_address<=0; staged_expected<=0; staged_mask<=0;
    end else if (transport_reset) begin
      // Runtime transport cancellation must not clear replay FAIL evidence,
      // counters, or staged data. The independent replay_reset records abort.
      aw_pending<=0; w_pending<=0; awaddr<=0; wdata<=0; wstrb<=0;
      s_axi_bvalid<=0; s_axi_bresp<=0; s_axi_rvalid<=0; s_axi_rresp<=0; s_axi_rdata<=0;
    end else begin
      if (s_axi_awvalid && s_axi_awready) begin awaddr<=s_axi_awaddr; aw_pending<=1; end
      if (s_axi_wvalid && s_axi_wready) begin
        wdata<=s_axi_wdata; wstrb<=s_axi_wstrb; w_pending<=1;
      end
      if (s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
      if (execute) begin
        aw_pending<=0; w_pending<=0; s_axi_bvalid<=1;
        s_axi_bresp<=(!in_window || malformed) ? 2'b10 : 2'b00;
        if (valid_write) begin
          case(awaddr)
            32'h910: begin staged_address<=wdata; staged_mask[0]<=1; end
            32'h914: begin staged_expected[31:0]<=wdata; staged_mask[1]<=1; end
            32'h918: begin staged_expected[63:32]<=wdata; staged_mask[2]<=1; end
            32'h91c: begin staged_expected[95:64]<=wdata; staged_mask[3]<=1; end
            32'h920: begin staged_expected[127:96]<=wdata; staged_mask[4]<=1; end
            32'h924: staged_mask<=0;
            default: ;
          endcase
        end
      end
      if (clear && state!=1) begin staged_address<=0; staged_expected<=0; staged_mask<=0; end
      if (s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
      if (s_axi_arvalid && s_axi_arready) begin
        s_axi_rvalid<=1; s_axi_rdata<=read_value; s_axi_rresp<=read_invalid ? 2'b10 : 2'b00;
      end
    end
  end
endmodule
`default_nettype wire
