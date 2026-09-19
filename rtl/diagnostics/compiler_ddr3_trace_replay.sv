`timescale 1ns/1ps
`default_nettype none
// TEMPORARY DIAGNOSTIC ONLY. Hand-written trace replay, not compiler output
// and not a production accelerator. Authentication is performed by the host.
module compiler_ddr3_trace_replay (
    input wire clk, reset, replay_reset, calib_complete,
    input wire clear, start, finish, configure, protocol_error,
    input wire [31:0] configured_count,
    input wire push,
    input wire [31:0] push_address,
    input wire [127:0] push_expected,
    output wire push_ready,
    output reg [1:0] state,
    output reg sealed,
    output wire starved,
    output reg [4:0] fifo_level,
    output reg [31:0] expected_count, pushed_count, accepted_count,
    output reg [31:0] response_count, checked_count, error_bits,
    output reg [31:0] first_index, first_address,
    output reg [127:0] first_expected, first_actual,
    output wire wb_cyc, wb_stb, wb_we,
    output wire [31:0] wb_addr,
    output wire [15:0] wb_sel,
    input wire wb_stall, wb_ack, wb_err,
    input wire [127:0] wb_rdata
);
  localparam [1:0] IDLE=0, RUN=1, PASS=2, FAIL=3;
  reg [31:0] fifo_address [0:15];
  reg [127:0] fifo_expected [0:15];
  reg [3:0] read_pointer, write_pointer;
  reg active, pending;
  reg [31:0] active_address;
  reg [127:0] active_expected;
  reg [31:0] failure;

  assign push_ready = (state==IDLE || state==RUN) && !sealed &&
                      expected_count!=0 && pushed_count<expected_count && fifo_level<16;
  assign starved = state==RUN && !active && fifo_level==0 && !sealed;
  assign wb_cyc = state==RUN && active && calib_complete && !replay_reset;
  assign wb_stb = wb_cyc && !pending;
  assign wb_we = 1'b0;
  assign wb_addr = active_address;
  assign wb_sel = 16'hffff;
  wire accept = wb_stb && !wb_stall;
  wire response = wb_cyc && (pending || accept) && (wb_ack || wb_err);
  wire enqueue = push && push_ready;

  // One priority decision captures a complete first-failure record atomically.
  // Once FAIL is latched, only CLEAR (or cold reset) can change this evidence.
  always @* begin
    failure = 0;
    if (state!=FAIL) begin
      if (state==RUN && (replay_reset || clear)) failure=32'h08;
      else if (state==RUN && !calib_complete) failure=32'h04;
      else if (protocol_error) failure=32'h80;
      else if (configure && (state!=IDLE || pushed_count!=0 || sealed)) failure=32'h80;
      else if (start && (state!=IDLE || !calib_complete || expected_count==0)) failure=32'h10;
      else if (finish && pushed_count!=expected_count) failure=32'h20;
      else if (push && (sealed || expected_count==0 || pushed_count>=expected_count || state==PASS)) failure=32'h40;
      else if (response && wb_err) failure=32'h02;
      else if (response && wb_rdata!=active_expected) failure=32'h01;
    end
  end

  always @(posedge clk) begin
    if (reset || (clear && state!=RUN)) begin
      state<=IDLE; sealed<=0; fifo_level<=0;
      expected_count<=0; pushed_count<=0; accepted_count<=0;
      response_count<=0; checked_count<=0; error_bits<=0;
      first_index<=32'hffffffff; first_address<=0; first_expected<=0; first_actual<=0;
      read_pointer<=0; write_pointer<=0; active<=0; pending<=0;
      active_address<=0; active_expected<=0;
    end else if (state!=FAIL) begin
      // Count actual bus events even if that response is the failure event.
      if (accept) accepted_count<=accepted_count+1;
      if (response) begin
        response_count<=response_count+1;
        if (!wb_err) checked_count<=checked_count+1;
      end
      if (failure!=0) begin
        state<=FAIL; error_bits<=failure;
        first_index<=checked_count;
        first_address<=active ? active_address : 32'd0;
        first_expected<=active ? active_expected : 128'd0;
        first_actual <= wb_rdata;
        active<=0; pending<=0;
      end else begin
        if (configure) expected_count<=configured_count;
        if (finish) sealed<=1;
        if (start) state<=RUN;
        if (enqueue) begin
          fifo_address[write_pointer]<=push_address;
          fifo_expected[write_pointer]<=push_expected;
          write_pointer<=write_pointer+1'b1;
          pushed_count<=pushed_count+1;
        end
        case ({enqueue,accept})
          2'b10: fifo_level<=fifo_level+1'b1;
          2'b01: fifo_level<=fifo_level-1'b1;
          default: ;
        endcase
        if (state==RUN) begin
          if (!active && fifo_level!=0) begin
            // Synchronous FIFO read into the only active request register.
            // The FIFO entry remains occupied until Wishbone acceptance.
            active_address <= fifo_address[read_pointer];
            active_expected<=fifo_expected[read_pointer];
            active<=1;
          end
          if (accept) begin
            read_pointer<=read_pointer+1'b1;
            pending<=1;
          end
          if (response) begin active<=0; pending<=0; end
          if (sealed && !active && fifo_level==0 && expected_count!=0 &&
              pushed_count==expected_count && accepted_count==expected_count &&
              response_count==expected_count && checked_count==expected_count)
            state<=PASS;
        end
      end
    end
  end
endmodule
`default_nettype wire
