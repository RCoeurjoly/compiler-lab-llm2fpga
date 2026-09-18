`timescale 1ps/1ps
module startup_tb;
  // Common zero-phase rising edges, matching the board PLL and upstream bench.
  reg controller_clk=1, ddr_clk=1, ddr_clk_90=1, ref_clk=1, reset_n=0;
  always #6000 controller_clk=~controller_clk;
  always #1500 ddr_clk=~ddr_clk;
  initial begin #750; forever #1500 ddr_clk_90=~ddr_clk_90; end
  always #2500 ref_clk=~ref_clk;
  wire calibrated;
  uberddr3_micron_memory dut (
    .controller_clk(controller_clk), .ddr_clk(ddr_clk), .ddr_clk_90(ddr_clk_90),
    .ref_clk(ref_clk), .reset_n(reset_n),
    .wb_cyc(1'b1), .wb_stb(1'b0), .wb_we(1'b0), .wb_addr(25'd0),
    .wb_wdata(128'd0), .wb_sel(16'hffff), .wb_stall(), .wb_ack(),
    .wb_err(), .wb_rdata(), .calibrated(calibrated)
  );
  longint unsigned cycles=0, max_cycles=1000000000;
  integer last_state=-1;
  time last_ddr_edge=0, last_controller_edge=0;
  always @(posedge ddr_clk) last_ddr_edge=$time;
  always @(posedge controller_clk) begin
    last_controller_edge=$time;
    #1;
    if (last_ddr_edge != last_controller_edge)
      $fatal(1, "FAIL: controller/DDR clock rising edges misaligned");
    if (cycles == 2) $display("PASS: physical clock phase alignment");
  end
  initial begin
    if ($value$plusargs("max_cycles=%d", max_cycles)) begin end
    repeat (10) @(negedge controller_clk);
    reset_n=1;
    $display("START: production reset released time_ps=%0t", $time);
  end
  always @(posedge controller_clk) begin
    cycles <= cycles+1;
    if (dut.controller.ddr3_controller_inst.state_calibrate !== last_state || cycles%100000==0) begin
      $display("PROGRESS: cycles=%0d time_ps=%0t state=%0d instruction=%0d write=%0d read=%0d correct=%0d wrong=%0d",
        cycles, $time, dut.controller.ddr3_controller_inst.state_calibrate,
        dut.controller.ddr3_controller_inst.instruction_address,
        dut.controller.ddr3_controller_inst.write_test_address_counter,
        dut.controller.ddr3_controller_inst.read_test_address_counter,
        dut.controller.ddr3_controller_inst.correct_read_data,
        dut.controller.ddr3_controller_inst.wrong_read_data);
      last_state=dut.controller.ddr3_controller_inst.state_calibrate;
    end
    if (reset_n && dut.controller.ddr3_controller_inst.wrong_read_data != 0)
      $fatal(1, "FAIL: BIST read mismatch cycles=%0d", cycles);
    if (calibrated === 1'b1) begin
      if (dut.controller.ddr3_controller_inst.wrong_read_data !== 0)
        $fatal(1, "FAIL: unknown/nonzero BIST errors");
      $display("PASS: startup calibration and BIST cycles=%0d time_ps=%0t", cycles, $time);
      $finish;
    end
    if (cycles >= max_cycles)
      $fatal(1, "FAIL: startup watchdog cycles=%0d calibrated=%b", cycles, calibrated);
  end
endmodule
