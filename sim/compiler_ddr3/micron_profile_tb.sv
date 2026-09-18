`timescale 1ps/1ps
module micron_profile_tb;
  reg ck=0, rst_n=0, cke=0;
`ifdef MICRON_NEGATIVE_MODEL_TIMING
  always #1500 ck=~ck;
`endif
  wire [15:0] dq;
  wire [1:0] dqs, dqs_n, tdqs_n;
  ddr3 #(.DEBUG(0)
`ifdef MICRON_PROFILE_WRONG_GEOMETRY
    , .ROW_BITS(16)
`endif
  )
  memory (
    .rst_n(rst_n), .ck(ck), .ck_n(~ck), .cke(cke),
    .cs_n(1'b1), .ras_n(1'b1), .cas_n(1'b1), .we_n(1'b1),
    .dm_tdqs(2'b0), .ba(3'b0), .addr(15'b0),
    .dq(dq), .dqs(dqs), .dqs_n(dqs_n), .tdqs_n(tdqs_n), .odt(1'b0)
  );
  initial begin
    #1;
    if (memory.ROW_BITS != 15 || memory.COL_BITS != 10 ||
        memory.BA_BITS != 3 || memory.DQ_BITS != 16 || memory.DQS_BITS != 2)
      $fatal(1, "FAIL: Micron geometry rows=%0d cols=%0d banks=%0d dq=%0d",
             memory.ROW_BITS, memory.COL_BITS, memory.BA_BITS, memory.DQ_BITS);
    if (memory.check_strict_timing != 1 || memory.check_strict_mrbits != 1 ||
        memory.DLL_OFF != 0)
      $fatal(1, "FAIL: Micron strict timing / mode checks disabled");
    $display("PASS: micron profile rows=15 cols=10 banks=3 dq=16 strict=1");
`ifdef MICRON_NEGATIVE_MODEL_TIMING
    // Deliberately violate production initialization waits at the memory pins.
    // The vendor model emits diagnostics via $display, not necessarily $fatal.
    #10000; rst_n=1; cke=1;
    #100000;
`endif
    $finish;
  end
endmodule
