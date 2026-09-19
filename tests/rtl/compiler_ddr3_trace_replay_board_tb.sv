`timescale 1ns/1ps
// Real pinned ingress, ingress CDC, loader FSM and owner mux. Only the PCIe
// endpoint, clock primitives and DDR controller are simulation boundary models.
module compiler_ddr3_trace_replay_board_tb;
 reg pcie_clk=0;always #8 pcie_clk=~pcie_clk;
 reg clk_50=0;always #10 clk_50=~clk_50;
 reg pcie_reset=1;
  reg [31:0] s_axi_awaddr=0;
  reg s_axi_awvalid=0;
  wire s_axi_awready=board.bar_awready;
  reg [31:0] s_axi_wdata=0;
  reg [3:0] s_axi_wstrb=0;
  reg s_axi_wvalid=0;
  wire s_axi_wready=board.bar_wready;
  wire [1:0] s_axi_bresp=board.bar_bresp;
  wire s_axi_bvalid=board.bar_bvalid;
  reg s_axi_bready=0;
  reg [31:0] s_axi_araddr=0;
  reg s_axi_arvalid=0;
  wire s_axi_arready=board.bar_arready;
  wire [31:0] s_axi_rdata=board.bar_rdata;
  wire [1:0] s_axi_rresp=board.bar_rresp;
  wire s_axi_rvalid=board.bar_rvalid;
  reg s_axi_rready=0;
 compiler_ddr3_trace_replay_top board(.clk_50(clk_50),.sys_rst_n(1'b1),
 .sys_clk_p(1'b0),.sys_clk_n(1'b0),.pci_exp_rxp(1'b0),.pci_exp_rxn(1'b0));
  task tick; @(posedge pcie_clk); #1; endtask
  task wr(input [31:0] address,input [31:0] data,input bit first=0);
    if(first) begin
      @(negedge pcie_clk); s_axi_wdata=data;s_axi_wstrb=15;s_axi_wvalid=1;
      do @(posedge pcie_clk); while(!s_axi_wready);
      @(negedge pcie_clk);s_axi_wvalid=0;
      repeat(2) tick();
      @(negedge pcie_clk);s_axi_awaddr=address;s_axi_awvalid=1;
      do @(posedge pcie_clk);while(!s_axi_awready);
      @(negedge pcie_clk);s_axi_awvalid=0;
    end else begin
      @(negedge pcie_clk);s_axi_awaddr=address;s_axi_awvalid=1;
      do @(posedge pcie_clk);while(!s_axi_awready);
      @(negedge pcie_clk);s_axi_awvalid=0;
      @(negedge pcie_clk);s_axi_wdata=data;s_axi_wstrb=15;s_axi_wvalid=1;
      do @(posedge pcie_clk);while(!s_axi_wready);
      @(negedge pcie_clk);s_axi_wvalid=0;
    end
    while(!s_axi_bvalid) tick();
    repeat(3) begin
      if(!s_axi_bvalid || s_axi_bresp) $fatal(1,"write backpressure response");
      tick();
    end
    @(negedge pcie_clk);s_axi_bready=1;tick();
    @(negedge pcie_clk);s_axi_bready=0;
  endtask
  task rd(input [31:0] address,input [31:0] want);
    @(negedge pcie_clk);s_axi_araddr=address;s_axi_arvalid=1;
    do @(posedge pcie_clk);while(!s_axi_arready);
    @(negedge pcie_clk);s_axi_arvalid=0;
    while(!s_axi_rvalid) tick();
    repeat(3) begin
      if(!s_axi_rvalid || s_axi_rresp || s_axi_rdata!==want)
        $fatal(1,"read %h expected %h got %h",address,want,s_axi_rdata);
      tick();
    end
    @(negedge pcie_clk);s_axi_rready=1;tick();
    @(negedge pcie_clk);s_axi_rready=0;
  endtask
  task push(input [31:0] address,input [127:0] data);
    wr('h910,address,1);wr('h914,data[31:0]);wr('h918,data[63:32],1);
    wr('h91c,data[95:64]);wr('h920,data[127:96]);wr('h924,1);
  endtask

 task command(input [7:0] opcode,input [31:0] address,input [127:0] data);
   $display("loader command opcode=%h address=%h",opcode,address);
   wr('h8,1);wr('h10,32'h33445244);wr('h14,{24'd0,opcode});wr('h18,address);
   wr('h20,data[31:0],1);wr('h24,data[63:32]);wr('h28,data[95:64]);wr('h2c,data[127:96]);
   wr('h30,1);
   // The unchanged production loader has a 1024-controller-cycle write drain.
   // Wait for its completion, rather than imposing a shorter fake DDR latency.
   repeat(30)tick();
   while(!board.rowstream_boot_done && !board.rowstream_loader_error) tick();
   if(!board.rowstream_boot_done || board.rowstream_loader_error)
     $fatal(1,"loader command did not complete opcode=%h address=%h",opcode,address);
 endtask
 integer i;
 localparam [127:0] BASE=128'hffeeddcc_bbaa9988_77665544_33221100;
 reg [127:0] expected;
 initial begin
   #250;@(negedge pcie_clk);pcie_reset=0;repeat(300)tick();
   rd(0,32'h54365043);rd(4,3);rd('h900,32'h52504c59);
   for(i=0;i<8;i=i+1) command(1,i,BASE+i);
   for(i=0;i<8;i=i+1) begin
     command(2,i,0);expected=BASE+i;
     rd('h44,expected[31:0]);rd('h48,expected[63:32]);rd('h4c,expected[95:64]);rd('h50,expected[127:96]);
   end
   wr('h90c,3);push(3,BASE+3);push(6,BASE+6);push(3,BASE+3);wr('h908,4);wr('h908,1);
   repeat(400)tick();rd('h928,2);rd('h940,3);
   wr('h908,2);command(2,7,0);rd('h44,32'h33221107);
   $display("PASS: full pinned loader shell BAR fixture");$finish;
 end
 initial begin #10000000;
   $display("state=%h done=%b error=%b ready=%b command=%h event=%b host_cyc=%b host_stb=%b stall=%b ack=%b pending=%b",board.rowstream_ddr3.read_probe_state_q,
     board.rowstream_loader_done,board.rowstream_loader_error,board.rowstream_calib_complete,
     board.rowstream_command_payload_q,board.rowstream_command_event_q,
     board.rowstream_ddr3.wb_cyc_to_controller,board.rowstream_ddr3.wb_stb_to_controller,
     board.rowstream_ddr3.wb_stall,board.rowstream_ddr3.wb_ack,board.rowstream_ddr3.uberddr3.pending);
   $fatal(1,"full board timeout");end
endmodule
// SPDX-License-Identifier: CERN-OHL-P
// Copyright 2024 regymm
`timescale 1ns / 1ps
//`define STOCK_APP

module pcie_7x_top_aximm # (
  parameter C_DATA_WIDTH        = 64, // RX/TX interface data width
  parameter KEEP_WIDTH          = C_DATA_WIDTH / 8, // TSTRB width
  parameter NO_RESET            = 0,
  parameter ENABLE_GEN2         = 0,
  parameter GT_DEVICE           = "GTX",
  parameter CFG_DEV_ID          = 16'h9999
) (
  output      pci_exp_txp,
  output      pci_exp_txn,
  input       pci_exp_rxp,
  input       pci_exp_rxn,

  input       sys_clk_p,
  input       sys_clk_n,
  input       sys_rst_n,

  //input       aux_clk_in,

  output      [3:0] led,
  output      task6_user_clk_o,
  output      task6_user_reset_o,
  output      task6_user_cfg_rst_n_o,
  output [31:0] task6_s_axi_awaddr_o,
  output        task6_s_axi_awvalid_o,
  input         task6_s_axi_awready_i,
  output [31:0] task6_s_axi_wdata_o,
  output [3:0]  task6_s_axi_wstrb_o,
  output        task6_s_axi_wvalid_o,
  input         task6_s_axi_wready_i,
  input  [1:0]  task6_s_axi_bresp_i,
  input         task6_s_axi_bvalid_i,
  output        task6_s_axi_bready_o,
  output [31:0] task6_s_axi_araddr_o,
  output        task6_s_axi_arvalid_o,
  input         task6_s_axi_arready_i,
  input  [31:0] task6_s_axi_rdata_i,
  input         task6_s_axi_rvalid_i,
  output        task6_s_axi_rready_o,
  input  [1:0]  task6_s_axi_rresp_i
);
  assign task6_user_clk_o=compiler_ddr3_trace_replay_board_tb.pcie_clk;
  assign task6_user_reset_o=compiler_ddr3_trace_replay_board_tb.pcie_reset;
  assign task6_user_cfg_rst_n_o=!compiler_ddr3_trace_replay_board_tb.pcie_reset;
  assign task6_s_axi_awaddr_o=compiler_ddr3_trace_replay_board_tb.s_axi_awaddr;
  assign task6_s_axi_awvalid_o=compiler_ddr3_trace_replay_board_tb.s_axi_awvalid;
  assign task6_s_axi_wdata_o=compiler_ddr3_trace_replay_board_tb.s_axi_wdata;
  assign task6_s_axi_wstrb_o=compiler_ddr3_trace_replay_board_tb.s_axi_wstrb;
  assign task6_s_axi_wvalid_o=compiler_ddr3_trace_replay_board_tb.s_axi_wvalid;
  assign task6_s_axi_bready_o=compiler_ddr3_trace_replay_board_tb.s_axi_bready;
  assign task6_s_axi_araddr_o=compiler_ddr3_trace_replay_board_tb.s_axi_araddr;
  assign task6_s_axi_arvalid_o=compiler_ddr3_trace_replay_board_tb.s_axi_arvalid;
  assign task6_s_axi_rready_o=compiler_ddr3_trace_replay_board_tb.s_axi_rready;
endmodule

////////////////////////////////////////////////////////////////////////////////
//
// Filename: ddr3_top.v
// Project: UberDDR3 - An Open Source DDR3 Controller
//
// Purpose: Top module which instantiates the ddr3_controller and ddr3_phy modules
// Use this as top module for instantiating UberDDR3 with Wishbone Interface.
//
// Engineer: Angelo C. Jacobo
//
////////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2023-2025  Angelo Jacobo
//
//     This program is free software: you can redistribute it and/or modify
//     it under the terms of the GNU General Public License as published by
//     the Free Software Foundation, either version 3 of the License, or
//     (at your option) any later version.
//
//     This program is distributed in the hope that it will be useful,
//     but WITHOUT ANY WARRANTY; without even the implied warranty of
//     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//     GNU General Public License for more details.
//
//     You should have received a copy of the GNU General Public License
//     along with this program.  If not, see <https://www.gnu.org/licenses/>.
//
////////////////////////////////////////////////////////////////////////////////

`default_nettype none
`timescale 1ns / 1ps

module ddr3_top #(
    parameter      CONTROLLER_CLK_PERIOD = 12_000, //ps, clock period of the controller interface
                   DDR3_CLK_PERIOD = 3_000, //ps, clock period of the DDR3 RAM device (must be 1/4 of the CONTROLLER_CLK_PERIOD)
                   ROW_BITS = 14,   //width of row address
                   COL_BITS = 10, //width of column address
                   BA_BITS = 3, //width of bank address
                   BYTE_LANES = 2, //number of byte lanes of DDR3 RAM
                   AUX_WIDTH = 4, //width of aux line (must be >= 4)
                   WB2_ADDR_BITS = 7, //width of 2nd wishbone address bus
                   WB2_DATA_BITS = 32, //width of 2nd wishbone data bus
                   DUAL_RANK_DIMM = 0, // enable dual rank DIMM (1 =  enable, 0 = disable)
    // DDR3 timing parameter values
    parameter      SPEED_BIN = 3, // 0 = Use top-level parameters , 1 = DDR3-1066 (7-7-7) , 2 = DR3-1333 (9-9-9) , 3 = DDR3-1600 (11-11-11)
                   SDRAM_CAPACITY = 5, // 0 = 256Mb, 1 = 512Mb, 2 = 1Gb, 3 = 2Gb, 4 = 4Gb, 5 = 8Gb, 6 = 16Gb
                   TRCD = 13_750, // ps Active to Read/Write command time (only used if SPEED_BIN = 0)
                   TRP = 13_750, // ps Precharge command period (only used if SPEED_BIN = 0)
                   TRAS = 35_000, // ps ACT to PRE command period (only used if SPEED_BIN = 0)
    parameter[0:0] MICRON_SIM = 0, //enable faster simulation for micron ddr3 model (shorten POWER_ON_RESET_HIGH and INITIAL_CKE_LOW)
                   ODELAY_SUPPORTED = 0, //set to 1 when ODELAYE2 is supported
                   SECOND_WISHBONE = 0, //set to 1 if 2nd wishbone for debugging is needed
                   DLL_OFF = 0, // 1 = DLL off for low frequency ddr3 clock (< 125MHz)
                   WB_ERROR = 0, // set to 1 to support Wishbone error (asserts at ECC double bit error)
    parameter[1:0] BIST_MODE = 1, // 0 = No BIST, 1 = run through all address space ONCE , 2 = run through all address space for every test (burst w/r, random w/r, alternating r/w)
    parameter[0:0] BIST_TEST_DATAMASK = 1, // 1 = include per-byte DM writes in BIST, 0 = all-byte writes only
    parameter[1:0] ECC_ENABLE = 0, // set to 1 or 2 to add ECC (1 = Side-band ECC per burst, 2 = Side-band ECC per 8 bursts , 3 = Inline ECC )
    parameter[1:0] DIC = 2'b00, //Output Driver Impedance Control (2'b00 = RZQ/6, 2'b01 = RZQ/7, RZQ = 240ohms) (only change when you know what you are doing)
    parameter[2:0] RTT_NOM = 3'b011, //RTT Nominal (3'b000 = disabled, 3'b001 = RZQ/4, 3'b010 = RZQ/2 , 3'b011 = RZQ/6, RZQ = 240ohms)  (only change when you know what you are doing)
    parameter[1:0] SELF_REFRESH = 2'b00, // 0 = use i_user_self_refresh input, 1 = Self-refresh mode is enabled after 64 controller clock cycles of no requests, 2 = 128 cycles, 3 = 256 cycles
    parameter // The next parameters act more like a localparam (since user does not have to set this manually) but was added here to simplify port declaration
                DQ_BITS = 8,  //device width (fixed to 8, if DDR3 is x16 then BYTE_LANES will be 2 while )
                serdes_ratio = 4, // this controller is fixed as a 4:1 memory controller (CONTROLLER_CLK_PERIOD/DDR3_CLK_PERIOD = 4)
                wb_addr_bits = ROW_BITS + COL_BITS + BA_BITS - $clog2(serdes_ratio*2) + DUAL_RANK_DIMM,
                wb_data_bits = DQ_BITS*BYTE_LANES*serdes_ratio*2,
                wb_sel_bits = wb_data_bits / 8,
                wb2_sel_bits = WB2_DATA_BITS / 8,
                //4 is the width of a single ddr3 command {cs_n, ras_n, cas_n, we_n} plus 3 (ck_en, odt, reset_n) plus bank bits plus row bits
                cmd_len = 4 + 3 + BA_BITS + ROW_BITS + 2*DUAL_RANK_DIMM
    )
    (
        input wire i_controller_clk, i_ddr3_clk, i_ref_clk, //i_controller_clk = CONTROLLER_CLK_PERIOD, i_ddr3_clk = DDR3_CLK_PERIOD, i_ref_clk = 200MHz
        input wire i_ddr3_clk_90, //required only when ODELAY_SUPPORTED is zero
        input wire i_rst_n,
        //
        // Wishbone inputs
        input wire i_wb_cyc, //bus cycle active (1 = normal operation, 0 = all ongoing transaction are to be cancelled)
        input wire i_wb_stb, //request a transfer
        input wire i_wb_we, //write-enable (1 = write, 0 = read)
        input wire[wb_addr_bits - 1:0] i_wb_addr, //burst-addressable {row,bank,col}
        input wire[wb_data_bits - 1:0] i_wb_data, //write data, for a 4:1 controller data width is 8 times the number of pins on the device
        input wire[wb_sel_bits - 1:0] i_wb_sel, //byte strobe for write (1 = write the byte)
        input wire[AUX_WIDTH - 1:0]  i_aux, //for AXI-interface compatibility (given upon strobe)
        // Wishbone outputs
        output wire o_wb_stall, //1 = busy, cannot accept requests
        output wire o_wb_ack, //1 = read/write request has completed
        output wire o_wb_err, //1 = Error due to ECC double bit error (fixed to 0 if WB_ERROR = 0)
        output wire[wb_data_bits - 1:0] o_wb_data, //read data, for a 4:1 controller data width is 8 times the number of pins on the device
        output wire[AUX_WIDTH - 1:0]  o_aux, //for AXI-interface compatibility (given upon strobe)
        //
        // Wishbone 2 (PHY) inputs
        input wire i_wb2_cyc, //bus cycle active (1 = normal operation, 0 = all ongoing transaction are to be cancelled)
        input wire i_wb2_stb, //request a transfer
        input wire i_wb2_we, //write-enable (1 = write, 0 = read)
        input wire[WB2_ADDR_BITS - 1:0] i_wb2_addr, // memory-mapped register to be accessed
        input wire[WB2_DATA_BITS - 1:0] i_wb2_data, //write data
        input wire[wb2_sel_bits - 1:0] i_wb2_sel, //byte strobe for write (1 = write the byte)
        // Wishbone 2 (Controller) outputs
        output wire o_wb2_stall, //1 = busy, cannot accept requests
        output wire o_wb2_ack, //1 = read/write request has completed
        output wire[WB2_DATA_BITS - 1:0] o_wb2_data, //read data
        //
        // DDR3 I/O Interface
        output wire[DUAL_RANK_DIMM:0] o_ddr3_clk_p, o_ddr3_clk_n,
        output wire o_ddr3_reset_n,
        output wire[DUAL_RANK_DIMM:0] o_ddr3_cke, // CKE
        output wire[DUAL_RANK_DIMM:0] o_ddr3_cs_n, // chip select signal
        output wire o_ddr3_ras_n, // RAS#
        output wire o_ddr3_cas_n, // CAS#
        output wire o_ddr3_we_n, // WE#
        output wire[ROW_BITS-1:0] o_ddr3_addr,
        output wire[BA_BITS-1:0] o_ddr3_ba_addr,
        inout wire[(DQ_BITS*BYTE_LANES)-1:0] io_ddr3_dq,
        inout wire[BYTE_LANES-1:0] io_ddr3_dqs, io_ddr3_dqs_n,
        output wire[BYTE_LANES-1:0] o_ddr3_dm,
        output wire[DUAL_RANK_DIMM:0] o_ddr3_odt, // on-die termination
        //
        // Done Calibration pin
        output wire o_calib_complete,
        // Debug outputs
        output wire[31:0] o_debug1,
//        output wire[31:0] o_debug2,
//        output wire[31:0] o_debug3,
//        output wire[(DQ_BITS*BYTE_LANES)/8-1:0] o_ddr3_debug_read_dqs_p,
//        output wire[(DQ_BITS*BYTE_LANES)/8-1:0] o_ddr3_debug_read_dqs_n
        //
        // User enabled self-refresh
        input wire i_user_self_refresh,
        output wire uart_tx
    );
  // Simulation-only delayed, single-outstanding physical memory boundary.
  // This does not model DDR3 electrical/calibration/timing behavior.
  reg [127:0] memory[0:31];
  reg ack=0;reg [127:0] data=0;reg [3:0] aux=0;
  reg pending=0;integer delay_count=0,i;
  assign o_wb_stall=pending;
  assign o_wb_ack=ack;assign o_wb_err=0;assign o_wb_data=data;assign o_aux=aux;
  assign o_calib_complete=i_rst_n;assign o_debug1=0;
  always @(posedge i_controller_clk) begin
    ack<=0;
    if(!i_rst_n) pending<=0;
    else begin
      if(i_wb_cyc && i_wb_stb && !o_wb_stall) begin
        if(i_wb_addr>=32) $fatal(1,"fixture address overflow");
        pending<=1;delay_count<=3;data<=memory[i_wb_addr];aux<=i_aux;
        if(i_wb_we) for(i=0;i<16;i=i+1)
          if(i_wb_sel[i]) memory[i_wb_addr][8*i+:8]<=i_wb_data[8*i+:8];
      end
      if(pending) begin
        if(delay_count==0) begin ack<=1;pending<=0;end
        else delay_count<=delay_count-1;
      end
    end
  end
endmodule


module PLLE2_BASE #(parameter BANDWIDTH=0,parameter CLKFBOUT_MULT=0,parameter CLKFBOUT_PHASE=0,parameter CLKIN1_PERIOD=0,parameter CLKOUT0_DIVIDE=0,parameter CLKOUT0_DUTY_CYCLE=0,parameter CLKOUT0_PHASE=0,parameter CLKOUT1_DIVIDE=0,parameter CLKOUT1_DUTY_CYCLE=0,parameter CLKOUT1_PHASE=0,parameter CLKOUT2_DIVIDE=0,parameter CLKOUT2_DUTY_CYCLE=0,parameter CLKOUT2_PHASE=0,parameter CLKOUT3_DIVIDE=0,parameter CLKOUT3_DUTY_CYCLE=0,parameter CLKOUT3_PHASE=0,parameter DIVCLK_DIVIDE=0,parameter REF_JITTER1=0,parameter STARTUP_WAIT=0)(
 input CLKFBIN,CLKIN1,PWRDWN,RST,output CLKFBOUT,CLKOUT0,CLKOUT1,CLKOUT3,CLKOUT4,CLKOUT5,
 output reg CLKOUT2=0, output reg LOCKED=0);
 always #6 CLKOUT2=~CLKOUT2;
 initial #90 LOCKED=1;
 assign CLKOUT0=CLKOUT2;assign CLKOUT1=CLKOUT2;assign CLKOUT3=CLKOUT2;assign CLKFBOUT=CLKOUT2;
endmodule
module BUFG(input I,output O);assign O=I;endmodule
module BSCANE2 #(parameter JTAG_CHAIN=1,DISABLE_JTAG=0)(
 output CAPTURE,DRCK,RESET,RUNTEST,SEL,SHIFT,TCK,TDI,TMS,UPDATE,input TDO);
 assign CAPTURE=0;assign DRCK=0;assign RESET=0;assign RUNTEST=0;
 assign SEL=0;assign SHIFT=0;assign TCK=0;assign TDI=0;assign TMS=0;assign UPDATE=0;
endmodule
