`default_nettype none
`timescale 1ps/1ps

// YPCB physical wrapper for the Q-table/DDR3 integration probe.  The probe's
// logical request is held at address zero and issued after calibration solely
// to keep the adapter in the mapped design; this is a device-routing shell,
// not a model-inference top.
module llm_q_uberddr3_ypcb (
  input wire clk50, input wire rst_n,
  output wire [0:0] ddr3_ck_p, ddr3_ck_n, output wire ddr3_reset_n,
  output wire [0:0] ddr3_cke, ddr3_cs_n, output wire ddr3_ras_n,
  output wire ddr3_cas_n, ddr3_we_n, output wire [14:0] ddr3_addr,
  output wire [2:0] ddr3_ba, inout wire [63:0] ddr3_dq,
  inout wire [7:0] ddr3_dqs_p, ddr3_dqs_n, output wire [0:0] ddr3_odt,
  output wire [2:0] led
);
  wire controller_clk, ddr3_clk, ref_clk, ddr3_clk_90, clk_locked;
  wire response_valid, response_error, calib_complete;
  wire [31:0] response_address;
  wire [7:0] response_data;
  (* keep *) wire read_valid = calib_complete;
  (* keep *) wire [31:0] read_address = 32'b0;

  clk_wiz clk_wiz_inst (
    .clk_in1(clk50), .clk_out1(controller_clk), .clk_out2(ddr3_clk),
    .clk_out3(ref_clk), .clk_out4(ddr3_clk_90), .reset(!rst_n),
    .locked(clk_locked));

  llm_q_uberddr3_probe probe (
    .controller_clk(controller_clk), .ddr3_clk(ddr3_clk), .ref_clk(ref_clk),
    .ddr3_clk_90(ddr3_clk_90), .rst_n(rst_n && clk_locked),
    .read_valid(read_valid), .read_address(read_address),
    .response_valid(response_valid), .response_address(response_address),
    .response_data(response_data), .response_error(response_error),
    .ddr3_ck_p(ddr3_ck_p), .ddr3_ck_n(ddr3_ck_n),
    .ddr3_reset_n(ddr3_reset_n), .ddr3_cke(ddr3_cke), .ddr3_cs_n(ddr3_cs_n),
    .ddr3_ras_n(ddr3_ras_n), .ddr3_cas_n(ddr3_cas_n), .ddr3_we_n(ddr3_we_n),
    .ddr3_addr(ddr3_addr), .ddr3_ba(ddr3_ba), .ddr3_dq(ddr3_dq),
    .ddr3_dqs_p(ddr3_dqs_p), .ddr3_dqs_n(ddr3_dqs_n), .ddr3_odt(ddr3_odt),
    .calib_complete(calib_complete));

  assign led[0] = calib_complete;
  assign led[1] = response_valid;
  assign led[2] = clk_locked;
endmodule
`default_nettype wire
