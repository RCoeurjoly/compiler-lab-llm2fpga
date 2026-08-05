`timescale 1ns/1ps

module tb;
  logic clk = 1'b0;
  logic reset = 1'b1;
  logic go = 1'b0;
  logic done;

  main dut (.clk(clk), .reset(reset), .go(go), .done(done));

  always #5 clk = ~clk;

  task automatic run_case(
      input logic [31:0] input_bits,
      input logic signed [7:0] expected,
      input string label
  );
    integer cycles;
    logic signed [7:0] observed;
    begin
      // Each value must be a separate transaction: reset all state, seed the
      // generated input memory, and then launch the top-level component.
      reset = 1'b1;
      go = 1'b0;
      repeat (3) @(posedge clk);
      @(negedge clk);
      dut.mem_0.mem[0] = input_bits;
      reset = 1'b0;
      go = 1'b1;

      cycles = 0;
      while (done !== 1'b1) begin
        @(posedge clk);
        cycles = cycles + 1;
        if (cycles > 128)
          $fatal(1, "FPTO_SI_TIMEOUT label=%s", label);
      end

      @(negedge clk);
      observed = $signed(dut.mem_1.mem[0]);
      $display(
          "FPTO_SI_CASE label=%s input_bits=0x%08h observed=%0d expected=%0d",
          label, input_bits, observed, expected);
      if (observed !== expected)
        $fatal(
            1,
            "FPTO_SI_MISMATCH label=%s input_bits=0x%08h observed=%0d expected=%0d",
            label, input_bits, observed, expected);

      go = 1'b0;
      @(posedge clk);
    end
  endtask

  initial begin
    run_case(32'h40866666, 8'sd4, "plus_4_2");
    run_case(32'hbfd9999a, -8'sd1, "minus_1_7");
    run_case(32'h42fe0000, 8'sd127, "plus_127");
    run_case(32'hc3000000, -8'sd128, "minus_128");
    $display("FPTO_SI_MRC_PASS");
    $finish;
  end
endmodule
