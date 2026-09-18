// Simulation wiring only: production controller/PHY, behavioral I/O primitives,
// and the unmodified Micron pin-level model. No transaction RAM or preload.
`timescale 1ps/1ps
module uberddr3_micron_memory (
  input wire controller_clk, ddr_clk, ddr_clk_90, ref_clk, reset_n,
  input wire wb_cyc, wb_stb, wb_we,
  input wire [24:0] wb_addr,
  input wire [127:0] wb_wdata,
  input wire [15:0] wb_sel,
  output wire wb_stall, wb_ack, wb_err,
  output wire [127:0] wb_rdata,
  output wire calibrated
);
  wire ck, ck_n, rst_n, cke, cs_n, ras_n, cas_n, we_n, odt;
  wire [14:0] addr;
  wire [2:0] ba;
  wire [15:0] dq;
  wire [1:0] dm, dqs, dqs_n;
  ddr3_top #(
    .CONTROLLER_CLK_PERIOD(12000), .DDR3_CLK_PERIOD(3000),
    .ROW_BITS(15), .COL_BITS(10), .BA_BITS(3), .BYTE_LANES(2),
    .AUX_WIDTH(4), .WB2_ADDR_BITS(7), .WB2_DATA_BITS(32),
    .DUAL_RANK_DIMM(0), .SPEED_BIN(1), .SDRAM_CAPACITY(4),
    .TRCD(13750), .TRP(13750), .TRAS(35000),
`ifdef MICRON_NEGATIVE_SHORTENED_STARTUP
    .MICRON_SIM(1),
`else
    .MICRON_SIM(0),
`endif
    .ODELAY_SUPPORTED(0), .SECOND_WISHBONE(0), .DLL_OFF(0),
    .WB_ERROR(0), .BIST_MODE(2), .BIST_TEST_DATAMASK(0), .ECC_ENABLE(0)
  ) controller (
    .i_controller_clk(controller_clk), .i_ddr3_clk(ddr_clk),
    .i_ddr3_clk_90(ddr_clk_90), .i_ref_clk(ref_clk), .i_rst_n(reset_n),
    .i_wb_cyc(wb_cyc), .i_wb_stb(wb_stb), .i_wb_we(wb_we),
    .i_wb_addr(wb_addr), .i_wb_data(wb_wdata), .i_wb_sel(wb_sel),
    .i_aux(wb_we ? 4'd0 : 4'd1), .o_aux(),
    .o_wb_stall(wb_stall), .o_wb_ack(wb_ack), .o_wb_err(wb_err), .o_wb_data(wb_rdata),
    .i_wb2_cyc(1'b0), .i_wb2_stb(1'b0), .i_wb2_we(1'b0),
    .i_wb2_addr(7'd0), .i_wb2_data(32'd0), .i_wb2_sel(4'd0),
    .o_wb2_stall(), .o_wb2_ack(), .o_wb2_data(),
    .o_ddr3_clk_p(ck), .o_ddr3_clk_n(ck_n), .o_ddr3_reset_n(rst_n),
    .o_ddr3_cke(cke), .o_ddr3_cs_n(cs_n), .o_ddr3_ras_n(ras_n),
    .o_ddr3_cas_n(cas_n), .o_ddr3_we_n(we_n), .o_ddr3_addr(addr),
    .o_ddr3_ba_addr(ba), .io_ddr3_dq(dq), .io_ddr3_dqs(dqs),
    .io_ddr3_dqs_n(dqs_n), .o_ddr3_dm(dm), .o_ddr3_odt(odt),
    .o_calib_complete(calibrated), .o_debug1(),
    .i_user_self_refresh(1'b0), .uart_tx()
  );
  // DEBUG suppresses informational per-beat chatter, not strict timing errors.
  ddr3 #(.DEBUG(0)) memory (
    .rst_n(rst_n), .ck(ck), .ck_n(ck_n), .cke(cke), .cs_n(cs_n),
    .ras_n(ras_n), .cas_n(cas_n), .we_n(we_n), .dm_tdqs(dm),
    .ba(ba), .addr(addr), .dq(dq), .dqs(dqs), .dqs_n(dqs_n), .tdqs_n(), .odt(odt)
  );
  initial begin
    #1;
    if (controller.MICRON_SIM != 0 || controller.BIST_MODE != 2 ||
        controller.CONTROLLER_CLK_PERIOD != 12000 || controller.DDR3_CLK_PERIOD != 3000 ||
        controller.ROW_BITS != 15 || controller.COL_BITS != 10 || controller.BA_BITS != 3 ||
        controller.BYTE_LANES != 2 || controller.SDRAM_CAPACITY != 4 ||
        controller.ddr3_controller_inst.wb_addr_bits_sim != 25)
      $fatal(1, "FAIL: controller profile");
    if (memory.ROW_BITS != 15 || memory.COL_BITS != 10 || memory.BA_BITS != 3 ||
        memory.DQ_BITS != 16 || memory.check_strict_timing != 1 ||
        memory.check_strict_mrbits != 1)
      $fatal(1, "FAIL: Micron geometry / strict checks");
    $display("PASS: controller profile MICRON_SIM=0 BIST_MODE=2 address_bits=25 clocks=12000/3000");
  end
endmodule
