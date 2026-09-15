`default_nettype none
`timescale 1ps/1ps

// One-table integration probe.  Clock generation and DDR pins are explicit so
// the same module can be used by the YPCB wrapper and by the UberDDR3 model.
module llm_q_uberddr3_probe (
  input wire controller_clk, input wire ddr3_clk, input wire ref_clk,
  input wire ddr3_clk_90, input wire rst_n,
  input wire read_valid, input wire [31:0] read_address,
  output wire response_valid, output wire [31:0] response_address,
  output wire [7:0] response_data, output wire response_error,
  output wire [0:0] ddr3_ck_p, ddr3_ck_n, output wire ddr3_reset_n,
  output wire [0:0] ddr3_cke, ddr3_cs_n, output wire ddr3_ras_n,
  output wire ddr3_cas_n, ddr3_we_n, output wire [14:0] ddr3_addr,
  output wire [2:0] ddr3_ba, inout wire [63:0] ddr3_dq,
  inout wire [7:0] ddr3_dqs_p, ddr3_dqs_n, output wire [0:0] ddr3_odt,
  output wire calib_complete
);
  wire wb_cyc, wb_stb, wb_we, wb_stall, wb_ack, wb_err;
  wire [31:0] wb_addr;
  wire [15:0] wb_sel;
  wire [127:0] wb_rdata;
  wire [1:0] ddr3_dm;
  wire [3:0] unused_aux;

  llm_ddr3_adapter_shell adapter (
    .clk(controller_clk), .rst(!rst_n), .read_valid(read_valid),
    .read_address(read_address), .response_valid(response_valid),
    .response_address(response_address), .response_data(response_data),
    .response_error(response_error), .wb_cyc(wb_cyc), .wb_stb(wb_stb),
    .wb_we(wb_we), .wb_addr(wb_addr), .wb_sel(wb_sel),
    .wb_accept(!wb_stall), .wb_ack(wb_ack), .wb_err(wb_err),
    .wb_rdata(wb_rdata));

  ddr3_top #(
    .CONTROLLER_CLK_PERIOD(12000), .DDR3_CLK_PERIOD(3000),
    .ROW_BITS(15), .COL_BITS(10), .BA_BITS(3), .BYTE_LANES(2),
    .AUX_WIDTH(4), .WB2_ADDR_BITS(32), .WB2_DATA_BITS(32),
    .MICRON_SIM(0), .ODELAY_SUPPORTED(0), .SECOND_WISHBONE(0),
    .BIST_MODE(2), .BIST_TEST_DATAMASK(0), .ECC_ENABLE(0),
    .SPEED_BIN(1), .SDRAM_CAPACITY(4)
  ) ddr3 (
    .i_controller_clk(controller_clk), .i_ddr3_clk(ddr3_clk),
    .i_ref_clk(ref_clk), .i_ddr3_clk_90(ddr3_clk_90), .i_rst_n(rst_n),
    .i_wb_cyc(wb_cyc), .i_wb_stb(wb_stb), .i_wb_we(wb_we),
    .i_wb_addr(wb_addr[24:0]), .i_wb_data(128'b0), .i_wb_sel(wb_sel),
    .i_aux(4'b0), .o_wb_stall(wb_stall), .o_wb_ack(wb_ack),
    .o_wb_err(wb_err), .o_wb_data(wb_rdata), .o_aux(unused_aux),
    .i_wb2_cyc(1'b0), .i_wb2_stb(1'b0), .i_wb2_we(1'b0),
    .i_wb2_addr(32'b0), .i_wb2_data(32'b0), .i_wb2_sel(4'b0),
    .o_wb2_stall(), .o_wb2_ack(), .o_wb2_data(),
    .o_ddr3_clk_p(ddr3_ck_p), .o_ddr3_clk_n(ddr3_ck_n),
    .o_ddr3_reset_n(ddr3_reset_n), .o_ddr3_cke(ddr3_cke),
    .o_ddr3_cs_n(ddr3_cs_n), .o_ddr3_ras_n(ddr3_ras_n),
    .o_ddr3_cas_n(ddr3_cas_n), .o_ddr3_we_n(ddr3_we_n),
    .o_ddr3_addr(ddr3_addr), .o_ddr3_ba_addr(ddr3_ba),
    .io_ddr3_dq(ddr3_dq[15:0]), .io_ddr3_dqs(ddr3_dqs_p[1:0]),
    .io_ddr3_dqs_n(ddr3_dqs_n[1:0]), .o_ddr3_dm(ddr3_dm),
    .o_ddr3_odt(ddr3_odt), .o_calib_complete(calib_complete),
    .o_debug_calib_gate(), .o_debug_phy_sync_rst(),
    .o_debug_phy_status(), .o_debug1(), .i_user_self_refresh(1'b0),
    .uart_tx());
endmodule
`default_nettype wire
