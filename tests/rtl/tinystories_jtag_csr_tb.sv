`timescale 1ns/1ps
module tinystories_jtag_csr_tb;
  reg clk = 0;
  always #5 clk = ~clk;
  reg tck = 0, reset = 0, sel = 1, shift = 0, capture = 0, update = 0, tdi = 0;
  // BSCANE2 DRCK follows TCK during Capture/Shift and stays high otherwise
  // while selected. In particular, Update-DR supplies no DRCK rising edge.
  wire drck = sel && ((capture || shift) ? tck : 1'b1);
  wire tdo, start, core_reset, valid, index, tap_reset;
  wire [15:0] p0, p1, p2, p3;
  wire [63:0] response;
  integer reset_pulses = 0;
  reg allow_start = 0, core_done = 0;
  always @(posedge clk) begin
    if (core_reset) reset_pulses <= reset_pulses + 1;
    if (start && !allow_start) $fatal(1, "CSR-only phase must never start inference");
  end
  tinystories_1m_jtag_csr dut (
    .sys_clk(clk), .sys_rst(reset), .core_start(start), .core_reset(core_reset),
    .core_valid(valid), .core_token_index(index), .prompt_0(p0), .prompt_1(p1),
    .prompt_2(p2), .prompt_3(p3), .core_token_id(index ? 16'd612 : 16'd11), .core_done(core_done),
    .model_init_done(1'b1), .response_word(response), .tap_reset(tap_reset),
    .scan_drck(drck), .scan_reset(reset), .scan_sel(sel), .scan_shift(shift),
    .scan_capture(capture), .scan_update(update), .scan_tdi(tdi), .scan_tdo(tdo)
  );
  task transaction(input [63:0] command, output [63:0] received);
    integer bit_index;
    begin
      capture = 1; #20; tck = 1; #20; tck = 0; #20;
      capture = 0; shift = 1;
      for (bit_index = 0; bit_index < 64; bit_index = bit_index + 1) begin
        tdi = command[bit_index]; #20;
        received[bit_index] = tdo;
        tck = 1; #20; tck = 0; #20;
      end
      shift = 0; #20;
      update = 1; #40; update = 0; #80;
    end
  endtask
  reg [63:0] received;
  integer run;
  initial begin
    #20; reset = 1; #100; reset = 0; #100;
    for (run = 0; run < 3; run = run + 1) begin
      transaction(64'h3000000000000000, received);
      if (response !== 64'h2800000000000000) $fatal(1, "status command lost: %h", response);
      transaction(64'h1000000000001d1e, received);
      if (received !== 64'h2800000000000000) $fatal(1, "bad captured status: %h", received);
      transaction(64'h1000000000010962, received);
      transaction(64'h1000000000020101, received);
      transaction(64'h1000000000030280, received);
      if ({p0,p1,p2,p3} !== 64'h1d1e096201010280) $fatal(1, "frozen prompt transfer failed: %h", {p0,p1,p2,p3});
      transaction(64'h6000000000000000, received);
      transaction(64'h6000000000010000, received);
      if (received !== 64'h1d1e) $fatal(1, "prompt 0 readback failed");
      transaction(64'h6000000000020000, received);
      if (received !== 64'h0962) $fatal(1, "prompt 1 readback failed");
      transaction(64'h6000000000030000, received);
      if (received !== 64'h0101) $fatal(1, "prompt 2 readback failed");
      transaction(64'h5000000000000000, received);
      if (received !== 64'h0280) $fatal(1, "prompt 3 readback failed");
      if ({p0,p1,p2,p3} !== 64'd0 || valid) $fatal(1, "reset failed");
    end
    if (reset_pulses != 3) $fatal(1, "expected three reset pulses");
    allow_start = 1;
    transaction(64'h2000000000000000, received);
    repeat (20) begin
      @(negedge clk);
      if (!start || !valid) $fatal(1, "Calyx requires START held until done");
    end
    core_done = 1;
    @(negedge clk);
    if (start || valid) $fatal(1, "START not released on completion");
    core_done = 0;
    transaction(64'h3000000000000000, received);
    transaction(64'h4000000000000000, received);
    if (received !== 64'h2c00000000000000) $fatal(1, "completion not latched");
    transaction(64'h3000000000000000, received);
    if (received !== 64'd11) $fatal(1, "first token readback failed");
    transaction(64'h2000000000000000, received);
    if (!start || !valid) $fatal(1, "second START failed");
    transaction(64'h5000000000000000, received);
    if (start || valid) $fatal(1, "reset did not cancel held START");
    $display("PASS: prompt/readback/reset and held START/completion with BSCANE2 DRCK behavior");
    $finish;
  end
  initial begin #1000000; $fatal(1, "timeout"); end
endmodule
