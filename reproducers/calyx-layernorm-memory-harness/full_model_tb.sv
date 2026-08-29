// Diagnostic testbench for a generated Calyx main module.
// Compile with the generated main.sv and -s main_tb.
module main_tb;
  logic clk = 0;
  // Start deasserted so the generated combinational one-hot checks see a
  // known state, then create an actual reset edge before the first clock.
  logic reset = 0;
  logic go = 0;
  wire done;
  main dut(.clk(clk), .reset(reset), .go(go), .done(done));
  always #1 clk = ~clk;

  integer i;
  integer mismatches;
  initial begin
    for (i = 0; i < 64; i = i + 1) begin
      dut.mem_0.mem[i] = (i[0] ? 32'hffff0000 : 32'h00010000);
      dut.mem_1.mem[i] = 32'h00010000;
      dut.mem_2.mem[i] = 32'h00000000;
      dut.mem_3.mem[i] = 32'h00000000;
    end
    #1 reset = 1;
    repeat (4) @(posedge clk);
    @(negedge clk);
    reset = 0;
    go = 1;
    repeat (2) @(posedge clk);
    @(negedge clk);
    // Keep go asserted during this diagnostic run: the generated wrapper
    // currently gates memory requests/responses with invoke0_go_out (= go).
    // This tests whether that gate is cutting off the internal schedule.
    repeat (200000) begin
      @(posedge clk);
      if (done) begin
        mismatches = 0;
        for (i = 0; i < 64; i = i + 1)
          if (dut.mem_3.mem[i] !== (i[0] ? 32'hffff0000 : 32'h00010000))
            mismatches = mismatches + 1;
        $display("{\"status\":\"done\",\"mismatches\":%0d,\"cycles_bound\":200000}", mismatches);
        if (mismatches != 0) $fatal(1);
        $finish;
      end
    end
    $display("{\"status\":\"timeout\",\"cycles_bound\":200000,\"fsm0\":%0d,\"fsm\":%0d,\"mem_done\":%b%b%b%b}",
      dut.main_1_instance.fsm0_out, dut.main_1_instance.fsm_out,
      dut.mem_0_done, dut.mem_1_done, dut.mem_2_done, dut.mem_3_done);
    $fatal(1);
  end
endmodule
