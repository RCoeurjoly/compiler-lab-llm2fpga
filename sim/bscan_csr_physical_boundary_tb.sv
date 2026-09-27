`timescale 1ns/1ps
// Replay the observed physical BSCANE2 boundary: the final TMS=1 clock exits
// Shift-DR without a DRCK/SHIFT edge, then UPDATE latches the partial word.
module bscan_csr_physical_boundary_tb;
  reg sys_clk = 0;
  reg scan_drck = 0, scan_reset = 0, scan_sel = 1;
  reg scan_shift = 0, scan_capture = 0, scan_update = 0, scan_tdi = 0;
  wire scan_tdo;
  wire [63:0] response_word;
  wire [15:0] prompt_0;
  wire core_start, core_reset, core_valid;
  wire [0:0] core_token_index;
  always #5 sys_clk = ~sys_clk;

  tinystories_1m_jtag_csr dut (
      .sys_clk(sys_clk), .sys_rst(scan_reset), .core_start(core_start),
      .core_reset(core_reset), .core_valid(core_valid),
      .core_token_index(core_token_index), .prompt_0(prompt_0),
      .prompt_1(), .prompt_2(), .prompt_3(), .core_token_id(16'd0),
      .core_done(1'b0), .model_init_done(1'b1), .response_word(response_word),
      .tap_reset(), .scan_drck(scan_drck), .scan_reset(scan_reset),
      .scan_sel(scan_sel), .scan_shift(scan_shift),
      .scan_capture(scan_capture), .scan_update(scan_update),
      .scan_tdi(scan_tdi), .scan_tdo(scan_tdo));

  task automatic exchange(input [63:0] command, output [63:0] observed);
    integer i;
    begin
      observed = 0;
      scan_capture = 1; #1 scan_drck = 1; #1 scan_drck = 0;
      scan_capture = 0; scan_shift = 1;
      // The last bit is presented with TMS=1 by the host, but the physical
      // primitive does not produce a final DRCK/SHIFT edge for it.
      for (i = 0; i < 63; i = i + 1) begin
        scan_tdi = command[i];
        observed[i] = scan_tdo;
        #1 scan_drck = 1; #1 scan_drck = 0;
      end
      scan_tdi = command[63];
      observed[63] = scan_tdo;
      scan_shift = 0; scan_update = 1; #1 scan_update = 0;
      repeat (8) @(posedge sys_clk);
    end
  endtask

  // Set up a known CSR response through the already verified 64-edge command
  // path.  The physical probe below isolates response capture/shift alignment;
  // it does not claim to model the board's UPDATE command reconstruction.
  task automatic command_full(input [63:0] command);
    integer i;
    begin
      scan_capture = 1; #1 scan_drck = 1; #1 scan_drck = 0;
      scan_capture = 0; scan_shift = 1;
      for (i = 0; i < 64; i = i + 1) begin
        scan_tdi = command[i];
        #1 scan_drck = 1; #1 scan_drck = 0;
      end
      scan_shift = 0; scan_update = 1; #1 scan_update = 0;
      repeat (8) @(posedge sys_clk);
    end
  endtask

  reg [63:0] observed;
  initial begin
    #1 scan_reset = 1; #20 scan_reset = 0;
    // The board returns the preceding command's response during the next
    // exchange.  A non-palindromic loopback detects any one-bit slip.
    command_full(64'h7123456789abcdef);
    if (response_word !== 64'h7123456789abcdef)
      $fatal(1, "command loopback update failed: %016x", response_word);
    exchange(64'h3000000000000000, observed);
    if (observed !== 64'h7123456789abcdef)
      $fatal(1, "physical loopback TDO shifted: %016x", observed);
    command_full(64'h3000000000000000);
    if (response_word !== 64'h2800000000000000)
      $fatal(1, "status command update failed: %016x", response_word);
    exchange(64'h3000000000000000, observed);
    if (observed !== 64'h2800000000000000)
      $fatal(1, "physical STATUS TDO shifted: %016x", observed);
    $display("PASS: physical BSCANE2 boundary returns exact loopback and STATUS words");
    $finish;
  end
endmodule
