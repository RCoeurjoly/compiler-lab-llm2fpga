`timescale 1ns/1ps

module rc_ddr3_transport_tb;
  logic clk = 1'b0;
  logic rst = 1'b1;
  logic req_valid, req_write;
  logic [31:0] req_byte_address;
  logic resp_valid, resp_error;
  logic [31:0] resp_rdata;
  logic wb_cyc, wb_stb, wb_we, wb_accept, wb_ack, wb_err;
  logic [31:0] wb_addr;
  logic [15:0] wb_sel;
  logic [127:0] wb_rdata;
  logic [127:0] ddr [0:3];
  logic pending;
  logic [31:0] pending_addr;
  integer stall_cycles;
  integer response_count;
  integer accepted_reads;
  logic [31:0] stalled_addr;
  logic [15:0] stalled_sel;
  logic last_resp_valid;
  logic last_resp_error;
  logic [31:0] last_resp_rdata;
  integer write_response;
  integer next_response;

  rc_ddr3_adapter dut (
    .clk, .rst, .req_valid, .req_write, .req_byte_address,
    .resp_valid, .resp_error, .resp_rdata,
    .wb_cyc, .wb_stb, .wb_we, .wb_addr, .wb_sel,
    .wb_accept, .wb_ack, .wb_err, .wb_rdata
  );

  always #5 clk = ~clk;

  always @(posedge clk) begin
    wb_accept <= 1'b0;
    wb_ack <= 1'b0;
    wb_err <= 1'b0;
    if (rst) begin
      pending <= 1'b0;
      stall_cycles <= 0;
      wb_rdata <= '0;
    end else if (pending) begin
      // wb_accept is still visible to the adapter on this edge; once it has
      // sampled that acceptance it must not issue another request.
      if ((wb_cyc || wb_stb) && !wb_accept)
        $fatal(1, "adapter issued a second read while one completion was outstanding");
      wb_ack <= 1'b1;
      wb_rdata <= ddr[pending_addr];
      pending <= 1'b0;
    end else if (wb_cyc && wb_stb) begin
      if (wb_we)
        $fatal(1, "read-only adapter asserted wb_we");
      if (stall_cycles != 0) begin
        if (wb_addr !== stalled_addr || wb_sel !== stalled_sel)
          $fatal(1, "adapter changed address or lane mask while backpressured");
        stall_cycles <= stall_cycles - 1;
      end else begin
        wb_accept <= 1'b1;
        accepted_reads <= accepted_reads + 1;
        pending_addr <= wb_addr;
        pending <= 1'b1;
      end
    end
  end

  // Observe completions between active clock edges, avoiding a race with the
  // registered DUT response pulse.  Adjacent observations make a widened
  // completion pulse an immediate test failure.
  always @(negedge clk) begin
    if (rst) begin
      response_count = 0;
      last_resp_valid = 1'b0;
    end else begin
      if (resp_valid) begin
        if (last_resp_valid)
          $fatal(1, "response completion was not a one-cycle pulse");
        response_count = response_count + 1;
        last_resp_error = resp_error;
        last_resp_rdata = resp_rdata;
      end
      last_resp_valid = resp_valid;
    end
  end

  task automatic start_read(input logic [31:0] address, input integer stalls);
    begin
      next_response = response_count + 1;
      @(negedge clk);
      req_byte_address = address;
      req_write = 1'b0;
      req_valid = 1'b1;
      stall_cycles = stalls;
      stalled_addr = address >> 4;
      stalled_sel = 16'h000f << address[3:0];
      @(negedge clk);
      req_valid = 1'b0;
    end
  endtask

  task automatic expect_response(input logic [31:0] expected, input logic error,
                                 input integer expected_count);
    integer timeout;
    begin
      timeout = 0;
      while (response_count < expected_count && timeout < 20) begin
        @(negedge clk);
        timeout = timeout + 1;
      end
      if (response_count != expected_count)
        $fatal(1, "timed out waiting for response");
      if (last_resp_error !== error || last_resp_rdata !== expected)
        $fatal(1, "response mismatch: error=%b data=%h expected error=%b data=%h",
               last_resp_error, last_resp_rdata, error, expected);
    end
  endtask

  initial begin
    req_valid = 1'b0;
    req_write = 1'b0;
    req_byte_address = '0;
    wb_accept = 1'b0;
    wb_ack = 1'b0;
    wb_err = 1'b0;
    wb_rdata = '0;
    pending = 1'b0;
    pending_addr = '0;
    stall_cycles = 0;
    response_count = 0;
    accepted_reads = 0;
    stalled_addr = '0;
    stalled_sel = '0;
    last_resp_valid = 1'b0;
    last_resp_error = 1'b0;
    last_resp_rdata = '0;
    ddr[0] = 128'h0f0e0d0c0b0a09080706050403020100;
    ddr[1] = 128'h1f1e1d1c1b1a19181716151413121110;
    ddr[2] = 128'h2f2e2d2c2b2a29282726252423222120;
    ddr[3] = 128'h3f3e3d3c3b3a39383736353433323130;

    repeat (2) @(posedge clk);
    if (wb_cyc || wb_stb || resp_valid)
      $fatal(1, "reset did not quiesce transport outputs");
    @(negedge clk);
    rst = 1'b0;

    // Exact low-lane translation, with input changes while the controller stalls.
    start_read(32'h00000000, 2);
    @(negedge clk);
    req_byte_address = 32'h0000001c;
    expect_response(32'h03020100, 1'b0, next_response);

    // A different 32-bit lane in the same 16-byte line and then the next line.
    start_read(32'h00000008, 1);
    expect_response(32'h0b0a0908, 1'b0, next_response);
    start_read(32'h00000010, 0);
    expect_response(32'h13121110, 1'b0, next_response);

    // Writes and accesses that straddle a 16-byte transport line are rejected
    // locally and must not become controller requests.
    @(negedge clk);
    write_response = response_count + 1;
    req_byte_address = 32'h00000004;
    req_write = 1'b1;
    req_valid = 1'b1;
    @(negedge clk);
    req_valid = 1'b0;
    expect_response(32'h00000000, 1'b1, write_response);
    if (wb_cyc || wb_stb)
      $fatal(1, "rejected write reached the DDR3 model");

    start_read(32'h0000000e, 0);
    expect_response(32'h00000000, 1'b1, next_response);
    if (response_count !== 5)
      $fatal(1, "completion ordering/count mismatch: %0d", response_count);
    if (accepted_reads !== 3)
      $fatal(1, "rejected requests or duplicates reached the DDR3 model: %0d", accepted_reads);
    $display("RC_DDR3_TRANSPORT_PASS responses=%0d", response_count);
    $finish;
  end
endmodule
