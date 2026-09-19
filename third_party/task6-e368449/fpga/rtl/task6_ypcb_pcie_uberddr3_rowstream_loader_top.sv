`timescale 1ns/1ps
`default_nettype none

module task6_ypcb_pcie_uberddr3_rowstream_loader_top #(
  parameter int DDR_BYTE_LANES = 2,
  parameter bit ENABLE_PCIE_TOP1 = 1'b1,
  parameter bit TINYSTORIES_LOADER_ONLY = 1'b0,
  parameter int TINYSTORIES_TMAX = 32,
  parameter bit TINYSTORIES_ENABLE_ENGINE = 1'b1,
  parameter bit TINYSTORIES_ENABLE_SERVICE = 1'b1,
  parameter bit TINYSTORIES_DIRECT_ACCELERATOR_OWNER = 1'b0,
  parameter bit ENABLE_PCIE_MLP_SELFTEST = 1'b0,
  parameter bit ENABLE_PCIE_MLP_ACCEL = ENABLE_PCIE_MLP_SELFTEST,
  parameter bit ENABLE_PCIE_M2_FULL_BLOCK_ACCEL = 1'b0
) (
  output wire        pci_exp_txp,
  output wire        pci_exp_txn,
  input  wire        pci_exp_rxp,
  input  wire        pci_exp_rxn,
  input  wire        sys_clk_p,
  input  wire        sys_clk_n,
  input  wire        sys_rst_n,
  input  wire        clk_50,
  output wire  [2:0] led,
  output wire [14:0] ddram_a,
  output wire  [2:0] ddram_ba,
  output wire        ddram_cas_n,
  output wire        ddram_cke,
  output wire        ddram_clk_n,
  output wire        ddram_clk_p,
  output wire        ddram_cs_n,
  inout  wire [DDR_BYTE_LANES * 8 - 1:0] ddram_dq,
  inout  wire [DDR_BYTE_LANES - 1:0] ddram_dqs_n,
  inout  wire [DDR_BYTE_LANES - 1:0] ddram_dqs_p,
  output wire        ddram_odt,
  output wire        ddram_ras_n,
  output wire        ddram_reset_n,
  output wire        ddram_we_n
);
  localparam int COMMAND_WIDTH = 208;

  wire pcie_user_clk;
  wire pcie_user_reset;
  wire pcie_user_cfg_rst_n;
  wire pcie_user_rst_n = !pcie_user_reset;
  wire rowstream_clk;
  wire rowstream_rst_n;
  wire [COMMAND_WIDTH - 1:0] rowstream_command_payload;
  wire rowstream_command_event;
  logic [COMMAND_WIDTH - 1:0] rowstream_command_payload_q;
  logic rowstream_command_event_q;
  wire rowstream_status_clear;
  wire rowstream_calib_complete;
  wire rowstream_boot_done;
  wire [31:0] rowstream_ddr_debug1;
  wire rowstream_loader_done;
  wire rowstream_loader_error;
  wire rowstream_loader_last_accepted;
  wire rowstream_loader_last_magic_ok;
  wire [7:0] rowstream_loader_last_opcode;
  wire [1:0] rowstream_loader_last_chunk;
  wire [31:0] rowstream_loader_command_payload_addr;
  wire [31:0] rowstream_loader_wait_cycles;
  wire [511:0] rowstream_loader_read_data;
  wire [511:0] rowstream_top1_hidden_vector;
  wire rowstream_top1_start;
  wire rowstream_top1_status_clear;
  wire rowstream_top1_busy;
  wire rowstream_top1_done;
  wire rowstream_top1_error;
  wire [31:0] rowstream_top1_token;
  wire [31:0] rowstream_top1_score_q024;
  wire [31:0] rowstream_top1_rows_scanned;
  wire [31:0] rowstream_top1_cycle_count;
  wire [31:0] rowstream_top1_debug_status;
  wire [31:0] rowstream_top1_debug_reader_addr;
  wire [31:0] rowstream_top1_debug_wb_ack_count;
  wire [31:0] rowstream_top1_debug_wb_err_count;
  wire [31:0] rowstream_top1_debug_packet_wb_write_ack_count;
  wire [31:0] rowstream_top1_debug_packet_wb_read_ack_count;
  wire rowstream_mlp_selftest_present;
  wire [31:0] rowstream_mlp_selftest_status;
  wire [31:0] rowstream_mlp_selftest_cycle_count;
  wire [31:0] rowstream_mlp_selftest_fail_detail;
  wire [31:0] rowstream_mlp_selftest_fail_values;
  wire [31:0] rowstream_mlp_selftest_first_add_sample;
  wire [31:0] rowstream_mlp_selftest_first_requant_sample;
  wire [31:0] rowstream_mlp_selftest_requant_debug0;
  wire [31:0] rowstream_mlp_selftest_requant_debug1;
  wire [31:0] rowstream_mlp_selftest_debug_select;
  wire [511:0] rowstream_mlp_accel_activation_vector;
  wire [511:0] rowstream_mlp_accel_residual_vector;
  wire rowstream_mlp_accel_start;
  wire rowstream_mlp_accel_clear;
  wire [31:0] rowstream_mlp_accel_status;
  wire [31:0] rowstream_mlp_accel_cycle_count;
  wire [31:0] rowstream_mlp_accel_output_checksum;
  wire [31:0] rowstream_mlp_accel_output_sample0;
  wire [31:0] rowstream_mlp_accel_output_sample1;
  wire [511:0] rowstream_mlp_accel_output_vector;
  wire [511:0] rowstream_m2_full_block_input_vector;
  wire [511:0] rowstream_m2_full_block_residual_vector;
  wire rowstream_m2_full_block_start;
  wire rowstream_m2_full_block_clear;
  wire [31:0] rowstream_m2_full_block_status;
  wire [31:0] rowstream_m2_full_block_cycle_count;
  wire [31:0] rowstream_m2_full_block_output_checksum;
  wire [31:0] rowstream_m2_full_block_output_sample0;
  wire [31:0] rowstream_m2_full_block_output_sample1;
  wire [31:0] rowstream_m2_full_block_output_count;
  wire [511:0] rowstream_m2_full_block_output_vector;

  // Register the CDC command bundle at the rowstream boundary. The ingress
  // guarantees payload/event alignment; this local stage keeps the wide
  // command decoder off the ingress register's timing path.
  always_ff @(posedge rowstream_clk or negedge rowstream_rst_n) begin
    if (!rowstream_rst_n) begin
      rowstream_command_payload_q <= '0;
      rowstream_command_event_q <= 1'b0;
    end else begin
      rowstream_command_payload_q <= rowstream_command_payload;
      rowstream_command_event_q <= rowstream_command_event;
    end
  end
`ifdef TASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS
  wire [15:0] rowstream_tinystories_prompt_token;
  wire [7:0] rowstream_tinystories_requested_tokens;
  wire [31:0] rowstream_tinystories_package_tag;
  wire rowstream_tinystories_prompt;
  wire rowstream_tinystories_start;
  wire rowstream_tinystories_clear;
  wire rowstream_tinystories_prompt_ready;
  wire rowstream_tinystories_busy;
  wire rowstream_tinystories_error;
  wire [7:0] rowstream_tinystories_error_code;
  wire [62:0] rowstream_tinystories_debug;
  wire rowstream_tinystories_bridge_error;
  wire [31:0] rowstream_tinystories_requests;
  wire [31:0] rowstream_tinystories_cache_hits;
  wire [31:0] rowstream_tinystories_cache_misses;
  wire [31:0] rowstream_tinystories_wb_reads;
  wire [31:0] rowstream_tinystories_stall_cycles;
  wire rowstream_tinystories_ddr_owner_active;
  wire rowstream_tinystories_ddr_accelerator_owned;
  wire rowstream_tinystories_token_valid;
  wire rowstream_tinystories_token_ready;
  wire [15:0] rowstream_tinystories_token_id;
`endif

  wire [3:0] pcie_led;
  assign led[0] = rowstream_boot_done;
  assign led[1] = rowstream_rst_n && !rowstream_boot_done;
  assign led[2] = pcie_led[2];

  wire [31:0] s_axi_awaddr;
  wire        s_axi_awvalid;
  wire        s_axi_awready;
  wire [31:0] s_axi_wdata;
  wire [3:0]  s_axi_wstrb;
  wire        s_axi_wvalid;
  wire        s_axi_wready;
  wire [1:0]  s_axi_bresp;
  wire        s_axi_bvalid;
  wire        s_axi_bready;
  wire [31:0] s_axi_araddr;
  wire        s_axi_arvalid;
  wire        s_axi_arready;
  wire [31:0] s_axi_rdata;
  wire        s_axi_rvalid;
  wire        s_axi_rready;
  wire [1:0]  s_axi_rresp;

  pcie_7x_top_aximm #(
    .NO_RESET(0),
    .ENABLE_GEN2(0),
    .GT_DEVICE("GTX"),
    .CFG_DEV_ID(16'h0480)
  ) pcie_7x_top_aximm_i (
    .pci_exp_txp(pci_exp_txp),
    .pci_exp_txn(pci_exp_txn),
    .pci_exp_rxp(pci_exp_rxp),
    .pci_exp_rxn(pci_exp_rxn),
    .sys_clk_p(sys_clk_p),
    .sys_clk_n(sys_clk_n),
    .sys_rst_n(sys_rst_n),
    .led(pcie_led),
    .task6_user_clk_o(pcie_user_clk),
    .task6_user_reset_o(pcie_user_reset),
    .task6_user_cfg_rst_n_o(pcie_user_cfg_rst_n),
    .task6_s_axi_awaddr_o(s_axi_awaddr),
    .task6_s_axi_awvalid_o(s_axi_awvalid),
    .task6_s_axi_awready_i(s_axi_awready),
    .task6_s_axi_wdata_o(s_axi_wdata),
    .task6_s_axi_wstrb_o(s_axi_wstrb),
    .task6_s_axi_wvalid_o(s_axi_wvalid),
    .task6_s_axi_wready_i(s_axi_wready),
    .task6_s_axi_bresp_i(s_axi_bresp),
    .task6_s_axi_bvalid_i(s_axi_bvalid),
    .task6_s_axi_bready_o(s_axi_bready),
    .task6_s_axi_araddr_o(s_axi_araddr),
    .task6_s_axi_arvalid_o(s_axi_arvalid),
    .task6_s_axi_arready_i(s_axi_arready),
    .task6_s_axi_rdata_i(s_axi_rdata),
    .task6_s_axi_rvalid_i(s_axi_rvalid),
    .task6_s_axi_rready_o(s_axi_rready),
    .task6_s_axi_rresp_i(s_axi_rresp)
  );

  task6_pcie_axil_rowstream_loader_ingress_cdc #(
    .COMMAND_WIDTH(COMMAND_WIDTH),
    .COMMAND_DATA_LSB(80)
  ) pcie_ingress (
    .pcie_clk(pcie_user_clk),
    .pcie_rst_n(pcie_user_rst_n),
    .rowstream_clk(rowstream_clk),
    .rowstream_rst_n(rowstream_rst_n),
    .s_axi_awaddr(s_axi_awaddr),
    .s_axi_awvalid(s_axi_awvalid),
    .s_axi_awready(s_axi_awready),
    .s_axi_wdata(s_axi_wdata),
    .s_axi_wstrb(s_axi_wstrb),
    .s_axi_wvalid(s_axi_wvalid),
    .s_axi_wready(s_axi_wready),
    .s_axi_bresp(s_axi_bresp),
    .s_axi_bvalid(s_axi_bvalid),
    .s_axi_bready(s_axi_bready),
    .s_axi_araddr(s_axi_araddr),
    .s_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(s_axi_arready),
    .s_axi_rdata(s_axi_rdata),
    .s_axi_rvalid(s_axi_rvalid),
    .s_axi_rready(s_axi_rready),
    .s_axi_rresp(s_axi_rresp),
    .rowstream_command_payload_o(rowstream_command_payload),
    .rowstream_command_event_o(rowstream_command_event),
    .rowstream_status_clear_o(rowstream_status_clear),
    .rowstream_calib_complete_i(rowstream_calib_complete),
    .rowstream_boot_done_i(rowstream_boot_done),
    .rowstream_ddr_debug1_i(rowstream_ddr_debug1),
    .rowstream_loader_done_i(rowstream_loader_done),
    .rowstream_loader_error_i(rowstream_loader_error),
    .rowstream_loader_last_accepted_i(rowstream_loader_last_accepted),
    .rowstream_loader_last_magic_ok_i(rowstream_loader_last_magic_ok),
    .rowstream_loader_last_opcode_i(rowstream_loader_last_opcode),
    .rowstream_loader_last_chunk_i(rowstream_loader_last_chunk),
    .rowstream_loader_command_payload_addr_i(rowstream_loader_command_payload_addr),
    .rowstream_loader_wait_cycles_i(rowstream_loader_wait_cycles),
    .rowstream_loader_read_data_i(rowstream_loader_read_data),
    .rowstream_top1_hidden_vector_o(rowstream_top1_hidden_vector),
    .rowstream_top1_start_o(rowstream_top1_start),
    .rowstream_top1_status_clear_o(rowstream_top1_status_clear),
    .rowstream_top1_busy_i(rowstream_top1_busy),
    .rowstream_top1_done_i(rowstream_top1_done),
    .rowstream_top1_error_i(rowstream_top1_error),
    .rowstream_top1_token_i(rowstream_top1_token),
    .rowstream_top1_score_q024_i(rowstream_top1_score_q024),
    .rowstream_top1_rows_scanned_i(rowstream_top1_rows_scanned),
    .rowstream_top1_cycle_count_i(rowstream_top1_cycle_count),
    .rowstream_top1_debug_status_i(rowstream_top1_debug_status),
    .rowstream_top1_debug_reader_addr_i(rowstream_top1_debug_reader_addr),
    .rowstream_top1_debug_wb_ack_count_i(rowstream_top1_debug_wb_ack_count),
    .rowstream_top1_debug_wb_err_count_i(rowstream_top1_debug_wb_err_count),
    .rowstream_top1_debug_packet_wb_write_ack_count_i(rowstream_top1_debug_packet_wb_write_ack_count),
    .rowstream_top1_debug_packet_wb_read_ack_count_i(rowstream_top1_debug_packet_wb_read_ack_count),
    .rowstream_mlp_selftest_present_i(rowstream_mlp_selftest_present),
    .rowstream_mlp_selftest_status_i(rowstream_mlp_selftest_status),
    .rowstream_mlp_selftest_cycle_count_i(rowstream_mlp_selftest_cycle_count),
    .rowstream_mlp_selftest_fail_detail_i(rowstream_mlp_selftest_fail_detail),
    .rowstream_mlp_selftest_fail_values_i(rowstream_mlp_selftest_fail_values),
    .rowstream_mlp_selftest_first_add_sample_i(rowstream_mlp_selftest_first_add_sample),
    .rowstream_mlp_selftest_first_requant_sample_i(rowstream_mlp_selftest_first_requant_sample),
    .rowstream_mlp_selftest_requant_debug0_i(rowstream_mlp_selftest_requant_debug0),
    .rowstream_mlp_selftest_requant_debug1_i(rowstream_mlp_selftest_requant_debug1),
    .rowstream_mlp_selftest_debug_select_o(rowstream_mlp_selftest_debug_select),
    .rowstream_mlp_accel_activation_vector_o(rowstream_mlp_accel_activation_vector),
    .rowstream_mlp_accel_residual_vector_o(rowstream_mlp_accel_residual_vector),
    .rowstream_mlp_accel_start_o(rowstream_mlp_accel_start),
    .rowstream_mlp_accel_clear_o(rowstream_mlp_accel_clear),
    .rowstream_mlp_accel_status_i(rowstream_mlp_accel_status),
    .rowstream_mlp_accel_cycle_count_i(rowstream_mlp_accel_cycle_count),
    .rowstream_mlp_accel_output_checksum_i(rowstream_mlp_accel_output_checksum),
    .rowstream_mlp_accel_output_sample0_i(rowstream_mlp_accel_output_sample0),
    .rowstream_mlp_accel_output_sample1_i(rowstream_mlp_accel_output_sample1),
    .rowstream_mlp_accel_output_vector_i(rowstream_mlp_accel_output_vector),
    .rowstream_m2_full_block_input_vector_o(rowstream_m2_full_block_input_vector),
    .rowstream_m2_full_block_residual_vector_o(rowstream_m2_full_block_residual_vector),
    .rowstream_m2_full_block_start_o(rowstream_m2_full_block_start),
    .rowstream_m2_full_block_clear_o(rowstream_m2_full_block_clear),
    .rowstream_m2_full_block_status_i(rowstream_m2_full_block_status),
    .rowstream_m2_full_block_cycle_count_i(rowstream_m2_full_block_cycle_count),
    .rowstream_m2_full_block_output_checksum_i(rowstream_m2_full_block_output_checksum),
    .rowstream_m2_full_block_output_sample0_i(rowstream_m2_full_block_output_sample0),
    .rowstream_m2_full_block_output_sample1_i(rowstream_m2_full_block_output_sample1),
    .rowstream_m2_full_block_output_count_i(rowstream_m2_full_block_output_count),
    .rowstream_m2_full_block_debug_i(32'd0),
    .rowstream_m2_full_block_debug1_i(32'd0),
    .rowstream_m2_full_block_debug2_i(32'd0),
    .rowstream_m2_full_block_debug3_i(32'd0),
    .rowstream_m2_full_block_provenance_i(32'd0),
    .rowstream_m2_full_block_output_vector_i(rowstream_m2_full_block_output_vector)
`ifdef TASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS
    ,.rowstream_tinystories_prompt_token_o(rowstream_tinystories_prompt_token)
    ,.rowstream_tinystories_requested_tokens_o(rowstream_tinystories_requested_tokens)
    ,.rowstream_tinystories_package_tag_o(rowstream_tinystories_package_tag)
    ,.rowstream_tinystories_prompt_o(rowstream_tinystories_prompt)
    ,.rowstream_tinystories_start_o(rowstream_tinystories_start)
    ,.rowstream_tinystories_clear_o(rowstream_tinystories_clear)
    ,.rowstream_tinystories_prompt_ready_i(rowstream_tinystories_prompt_ready)
    ,.rowstream_tinystories_busy_i(rowstream_tinystories_busy)
    ,.rowstream_tinystories_error_i(rowstream_tinystories_error)
    ,.rowstream_tinystories_error_code_i(rowstream_tinystories_error_code)
    ,.rowstream_tinystories_debug_i(rowstream_tinystories_debug[31:0])
    ,.rowstream_tinystories_bridge_error_i(rowstream_tinystories_bridge_error)
    ,.rowstream_tinystories_requests_i(rowstream_tinystories_requests)
    ,.rowstream_tinystories_cache_hits_i(rowstream_tinystories_cache_hits)
    ,.rowstream_tinystories_cache_misses_i(rowstream_tinystories_cache_misses)
    ,.rowstream_tinystories_stall_cycles_i(rowstream_tinystories_stall_cycles)
    ,.rowstream_tinystories_token_valid_i(rowstream_tinystories_token_valid)
    ,.rowstream_tinystories_token_ready_o(rowstream_tinystories_token_ready)
    ,.rowstream_tinystories_token_id_i(rowstream_tinystories_token_id)
`endif
  );

  generate
    if (ENABLE_PCIE_MLP_SELFTEST) begin : gen_pcie_mlp_selftest
      task6_int8_l2_mlp_chain_residual_add_selftest_top #(
        .DEBUG_LEDS(0),
        .ENABLE_JTAG_DEBUG(1),
        .JTAG_CHAIN(4)
      ) mlp_selftest (
        .SYS_CLK(rowstream_clk),
        .SYS_RSTN(rowstream_rst_n),
        .led_3bits_tri_o(),
        .pcie_status_o(rowstream_mlp_selftest_status),
        .pcie_cycle_count_o(rowstream_mlp_selftest_cycle_count),
        .pcie_fail_detail_o(rowstream_mlp_selftest_fail_detail),
        .pcie_fail_values_o(rowstream_mlp_selftest_fail_values),
        .pcie_first_add_sample_o(rowstream_mlp_selftest_first_add_sample),
        .pcie_first_requant_sample_o(rowstream_mlp_selftest_first_requant_sample),
        .pcie_requant_debug0_o(rowstream_mlp_selftest_requant_debug0),
        .pcie_requant_debug1_o(rowstream_mlp_selftest_requant_debug1),
        .pcie_debug_select_i(rowstream_mlp_selftest_debug_select),
        .pcie_accel_activation_i(rowstream_mlp_accel_activation_vector),
        .pcie_accel_residual_i(rowstream_mlp_accel_residual_vector),
        .pcie_accel_start_pulse_i(rowstream_mlp_accel_start),
        .pcie_accel_clear_pulse_i(rowstream_mlp_accel_clear),
        .pcie_accel_status_o(rowstream_mlp_accel_status),
        .pcie_accel_cycle_count_o(rowstream_mlp_accel_cycle_count),
        .pcie_accel_output_checksum_o(rowstream_mlp_accel_output_checksum),
        .pcie_accel_output_sample0_o(rowstream_mlp_accel_output_sample0),
        .pcie_accel_output_sample1_o(rowstream_mlp_accel_output_sample1),
        .pcie_accel_output_vector_o(rowstream_mlp_accel_output_vector)
      );
      assign rowstream_mlp_selftest_present = 1'b1;
    end else if (ENABLE_PCIE_MLP_ACCEL) begin : gen_pcie_mlp_accel
      task6_int8_l2_mlp_chain_residual_add_accel_top mlp_accel (
        .SYS_CLK(rowstream_clk),
        .SYS_RSTN(rowstream_rst_n),
        .pcie_accel_activation_i(rowstream_mlp_accel_activation_vector),
        .pcie_accel_residual_i(rowstream_mlp_accel_residual_vector),
        .pcie_accel_start_pulse_i(rowstream_mlp_accel_start),
        .pcie_accel_clear_pulse_i(rowstream_mlp_accel_clear),
        .pcie_accel_status_o(rowstream_mlp_accel_status),
        .pcie_accel_cycle_count_o(rowstream_mlp_accel_cycle_count),
        .pcie_accel_output_checksum_o(rowstream_mlp_accel_output_checksum),
        .pcie_accel_output_sample0_o(rowstream_mlp_accel_output_sample0),
        .pcie_accel_output_sample1_o(rowstream_mlp_accel_output_sample1),
        .pcie_accel_output_vector_o(rowstream_mlp_accel_output_vector)
      );
      assign rowstream_mlp_selftest_present = 1'b1;
      assign rowstream_mlp_selftest_status = 32'h4d4c4150;
      assign rowstream_mlp_selftest_cycle_count = rowstream_mlp_accel_cycle_count;
      assign rowstream_mlp_selftest_fail_detail = 32'd0;
      assign rowstream_mlp_selftest_fail_values = 32'd0;
      assign rowstream_mlp_selftest_first_add_sample = rowstream_mlp_accel_output_sample0;
      assign rowstream_mlp_selftest_first_requant_sample = rowstream_mlp_accel_output_sample1;
      assign rowstream_mlp_selftest_requant_debug0 = 32'd0;
      assign rowstream_mlp_selftest_requant_debug1 = 32'd0;
    end else begin : gen_no_pcie_mlp_selftest
      assign rowstream_mlp_selftest_present = 1'b0;
      assign rowstream_mlp_selftest_status = 32'd0;
      assign rowstream_mlp_selftest_cycle_count = 32'd0;
      assign rowstream_mlp_selftest_fail_detail = 32'd0;
      assign rowstream_mlp_selftest_fail_values = 32'd0;
      assign rowstream_mlp_selftest_first_add_sample = 32'd0;
      assign rowstream_mlp_selftest_first_requant_sample = 32'd0;
      assign rowstream_mlp_selftest_requant_debug0 = 32'd0;
      assign rowstream_mlp_selftest_requant_debug1 = 32'd0;
      assign rowstream_mlp_accel_status = 32'd0;
      assign rowstream_mlp_accel_cycle_count = 32'd0;
      assign rowstream_mlp_accel_output_checksum = 32'd0;
      assign rowstream_mlp_accel_output_sample0 = 32'd0;
      assign rowstream_mlp_accel_output_sample1 = 32'd0;
      assign rowstream_mlp_accel_output_vector = 512'd0;
    end
  endgenerate

  generate
    if (ENABLE_PCIE_M2_FULL_BLOCK_ACCEL) begin : gen_pcie_m2_full_block_accel
      task6_m2_full_block_replay_accel_top m2_full_block_accel (
        .SYS_CLK(rowstream_clk),
        .SYS_RSTN(rowstream_rst_n),
        .pcie_block_input_i(rowstream_m2_full_block_input_vector),
        .pcie_residual_after_attention_i(rowstream_m2_full_block_residual_vector),
        .pcie_start_pulse_i(rowstream_m2_full_block_start),
        .pcie_clear_pulse_i(rowstream_m2_full_block_clear),
        .pcie_status_o(rowstream_m2_full_block_status),
        .pcie_cycle_count_o(rowstream_m2_full_block_cycle_count),
        .pcie_output_checksum_o(rowstream_m2_full_block_output_checksum),
        .pcie_output_sample0_o(rowstream_m2_full_block_output_sample0),
        .pcie_output_sample1_o(rowstream_m2_full_block_output_sample1),
        .pcie_output_count_o(rowstream_m2_full_block_output_count),
        .pcie_output_vector_o(rowstream_m2_full_block_output_vector)
      );
    end else begin : gen_no_pcie_m2_full_block_accel
      assign rowstream_m2_full_block_status = 32'd0;
      assign rowstream_m2_full_block_cycle_count = 32'd0;
      assign rowstream_m2_full_block_output_checksum = 32'd0;
      assign rowstream_m2_full_block_output_sample0 = 32'd0;
      assign rowstream_m2_full_block_output_sample1 = 32'd0;
      assign rowstream_m2_full_block_output_count = 32'd0;
      assign rowstream_m2_full_block_output_vector = 512'd0;
    end
  endgenerate

  task6_ypcb_uberddr3_bist_rowstream_loader_top #(
    .BYTE_LANES(DDR_BYTE_LANES),
    .JTAG_CHAIN(3),
    .JTAG_COMMAND_CHAIN(2),
    .DISABLE_JTAG_DEBUG_SHIFT(1),
    .BOOT_ISOLATE_UNTIL_CALIB(1),
    .PLL_FB_MULT(20),
    .PLL_CLKOUT0_DIVIDE(3),
    .PLL_CLKOUT1_DIVIDE(3),
    .PLL_CLKOUT2_DIVIDE(12),
    .PLL_CLKOUT3_DIVIDE(5),
    .CONTROLLER_CLK_PERIOD_PS(12_000),
    .DDR3_CLK_PERIOD_PS(3_000),
    .DLL_OFF_PARAM(1'b0),
    .SPEED_BIN_PARAM(1),
    .SDRAM_CAPACITY_PARAM(4),
    .BIST_MODE_PARAM(2),
    .BIST_TEST_DATAMASK(1'b0),
    .ENABLE_PCIE_TOP1(ENABLE_PCIE_TOP1),
    .TINYSTORIES_LOADER_ONLY(TINYSTORIES_LOADER_ONLY),
    .TINYSTORIES_TMAX(TINYSTORIES_TMAX),
    .TINYSTORIES_ENABLE_ENGINE(TINYSTORIES_ENABLE_ENGINE)
    ,.TINYSTORIES_ENABLE_SERVICE(TINYSTORIES_ENABLE_SERVICE)
    ,.TINYSTORIES_DIRECT_ACCELERATOR_OWNER(TINYSTORIES_DIRECT_ACCELERATOR_OWNER)
  ) rowstream_ddr3 (
    .clk50(clk_50),
    .SYS_RSTN(sys_rst_n),
    .ddram_a(ddram_a),
    .ddram_ba(ddram_ba),
    .ddram_cas_n(ddram_cas_n),
    .ddram_cke(ddram_cke),
    .ddram_clk_n(ddram_clk_n),
    .ddram_clk_p(ddram_clk_p),
    .ddram_cs_n(ddram_cs_n),
    .ddram_dq(ddram_dq),
    .ddram_dqs_n(ddram_dqs_n),
    .ddram_dqs_p(ddram_dqs_p),
    .ddram_odt(ddram_odt),
    .ddram_ras_n(ddram_ras_n),
    .ddram_reset_n(ddram_reset_n),
    .ddram_we_n(ddram_we_n),
    .pcie_command_payload_i(rowstream_command_payload_q),
    .pcie_command_event_i(rowstream_command_event_q),
    .pcie_status_clear_i(rowstream_status_clear),
    .pcie_controller_clk_o(rowstream_clk),
    .pcie_controller_rst_n_o(rowstream_rst_n),
    .pcie_calib_complete_o(rowstream_calib_complete),
    .pcie_boot_done_o(rowstream_boot_done),
    .pcie_ddr_debug1_o(rowstream_ddr_debug1),
    .pcie_loader_done_o(rowstream_loader_done),
    .pcie_loader_error_o(rowstream_loader_error),
    .pcie_loader_last_accepted_o(rowstream_loader_last_accepted),
    .pcie_loader_last_magic_ok_o(rowstream_loader_last_magic_ok),
    .pcie_loader_last_opcode_o(rowstream_loader_last_opcode),
    .pcie_loader_last_chunk_o(rowstream_loader_last_chunk),
    .pcie_loader_command_payload_addr_o(rowstream_loader_command_payload_addr),
    .pcie_loader_wait_cycles_o(rowstream_loader_wait_cycles),
    .pcie_loader_read_data_o(rowstream_loader_read_data),
    .pcie_top1_hidden_vector_i(rowstream_top1_hidden_vector),
    .pcie_top1_start_i(rowstream_top1_start),
    .pcie_top1_status_clear_i(rowstream_top1_status_clear),
    .pcie_top1_busy_o(rowstream_top1_busy),
    .pcie_top1_done_o(rowstream_top1_done),
    .pcie_top1_error_o(rowstream_top1_error),
    .pcie_top1_token_o(rowstream_top1_token),
    .pcie_top1_score_q024_o(rowstream_top1_score_q024),
    .pcie_top1_rows_scanned_o(rowstream_top1_rows_scanned),
    .pcie_top1_cycle_count_o(rowstream_top1_cycle_count),
    .pcie_top1_debug_status_o(rowstream_top1_debug_status),
    .pcie_top1_debug_reader_addr_o(rowstream_top1_debug_reader_addr),
    .pcie_top1_debug_wb_ack_count_o(rowstream_top1_debug_wb_ack_count),
    .pcie_top1_debug_wb_err_count_o(rowstream_top1_debug_wb_err_count),
    .pcie_top1_debug_packet_wb_write_ack_count_o(rowstream_top1_debug_packet_wb_write_ack_count),
    .pcie_top1_debug_packet_wb_read_ack_count_o(rowstream_top1_debug_packet_wb_read_ack_count)
`ifdef TASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS
    ,.tinystories_clear_i(rowstream_tinystories_clear)
    ,.tinystories_prompt_valid_i(rowstream_tinystories_prompt)
    ,.tinystories_prompt_ready_o(rowstream_tinystories_prompt_ready)
    ,.tinystories_prompt_token_i(rowstream_tinystories_prompt_token)
    ,.tinystories_start_i(rowstream_tinystories_start)
    ,.tinystories_requested_tokens_i(rowstream_tinystories_requested_tokens[5:0])
    ,.tinystories_package_tag_i(rowstream_tinystories_package_tag)
    ,.tinystories_token_valid_o(rowstream_tinystories_token_valid)
    ,.tinystories_token_ready_i(rowstream_tinystories_token_ready)
    ,.tinystories_token_id_o(rowstream_tinystories_token_id)
    ,.tinystories_busy_o(rowstream_tinystories_busy)
    ,.tinystories_error_o(rowstream_tinystories_error)
    ,.tinystories_error_code_o(rowstream_tinystories_error_code)
    ,.tinystories_debug_status_o(rowstream_tinystories_debug)
    ,.tinystories_bridge_error_o(rowstream_tinystories_bridge_error)
    ,.tinystories_request_count_o(rowstream_tinystories_requests)
    ,.tinystories_cache_hit_count_o(rowstream_tinystories_cache_hits)
    ,.tinystories_cache_miss_count_o(rowstream_tinystories_cache_misses)
    ,.tinystories_wb_read_count_o(rowstream_tinystories_wb_reads)
    ,.tinystories_wb_stall_cycle_count_o(rowstream_tinystories_stall_cycles)
    ,.tinystories_ddr_owner_active_o(rowstream_tinystories_ddr_owner_active)
    ,.tinystories_ddr_accelerator_owned_o(rowstream_tinystories_ddr_accelerator_owned)
`endif
  );

endmodule

`default_nettype wire
