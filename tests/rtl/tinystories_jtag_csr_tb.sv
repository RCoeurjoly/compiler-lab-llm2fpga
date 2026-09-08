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
  always @(posedge clk) begin
    if (core_reset) reset_pulses <= reset_pulses + 1;
    if (start) $fatal(1, "CSR-only test must never start inference");
  end
  tinystories_1m_jtag_csr dut (
    .sys_clk(clk), .sys_rst(reset), .core_start(start), .core_reset(core_reset),
    .core_valid(valid), .core_token_index(index), .prompt_0(p0), .prompt_1(p1),
    .prompt_2(p2), .prompt_3(p3), .core_token_id(16'd0), .core_done(1'b0),
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
      transaction(64'h1000000000000001, received);
      if (received !== 64'h2800000000000000) $fatal(1, "bad captured status: %h", received);
      transaction(64'h1000000000000012, received);
      transaction(64'h1000000000000023, received);
      transaction(64'h1000000000000034, received);
      // These values respect the existing overlapping index/value ABI.
      if ({p0,p1,p2,p3} !== 64'h0001001200230034) $fatal(1, "prompt transfer failed");
      transaction(64'h5000000000000000, received);
      if ({p0,p1,p2,p3} !== 64'd0 || valid) $fatal(1, "reset failed");
    end
    if (reset_pulses != 3) $fatal(1, "expected three reset pulses");
    $display("PASS: three status/prompt/reset sequences with BSCANE2 DRCK behavior");
    $finish;
  end
  initial begin #1000000; $fatal(1, "timeout"); end
endmodule
