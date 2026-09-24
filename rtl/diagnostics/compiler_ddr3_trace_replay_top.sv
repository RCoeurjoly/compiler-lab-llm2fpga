`timescale 1ns/1ps
`default_nettype none

// Derived wrapper wiring from pinned e368449; PCIe/UberDDR3 remain unchanged.
module compiler_ddr3_trace_replay_top #(
  parameter int DDR_BYTE_LANES = 2,
  parameter bit ENABLE_PCIE_TOP1 = 1'b0,
  parameter bit ENABLE_COMPILER_ACCELERATOR = 1'b0,
  // The trace CSR is required only by the temporary exact-sequence replay
  // diagnostic. Production inference keeps the PCIe loader/command path but
  // removes this wide debug register bank from the timing-critical design.
  parameter bit ENABLE_TRACE_REPLAY_CSR = 1'b1,
  parameter bit TINYSTORIES_LOADER_ONLY = 1'b0,
  parameter int TINYSTORIES_TMAX = 32,
  parameter bit TINYSTORIES_ENABLE_ENGINE = 1'b0,
  parameter bit TINYSTORIES_ENABLE_SERVICE = 1'b0,
  parameter bit TINYSTORIES_DIRECT_ACCELERATOR_OWNER = 1'b0,
  parameter bit ENABLE_PCIE_MLP_SELFTEST = 1'b0,
  parameter bit ENABLE_PCIE_MLP_ACCEL = ENABLE_PCIE_MLP_SELFTEST,
  parameter bit ENABLE_PCIE_M2_FULL_BLOCK_ACCEL = 1'b0,
  // Select the compiler-generated RC transport shell.  The legacy command
  // adapter remains the default diagnostic path; this option never reuses its
  // compute RTL.
  parameter bit ENABLE_COMPILER_GENERATED_RC = 1'b0
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
  wire compiler_prompt_ready, compiler_token_valid, compiler_token_ready;
  wire [15:0] compiler_token_id;
  wire compiler_busy, compiler_error;
  wire [7:0] compiler_error_code;
  wire [62:0] compiler_debug_status;
  wire [31:0] compiler_request_count;
  wire ingress_tinystories_token_ready;
  // Ports of the compiler-generated RC wrapper.  The wrapper is supplied by
  // the pipeline build; this top only connects its transport and token ABI.
  wire rc_done;
  wire rc_wb_cyc, rc_wb_stb;
  wire [31:0] rc_wb_addr;
  wire [15:0] rc_wb_sel;
  wire [7:0] rc_result0, rc_result1;
  wire [127:0] rc_token_data = {112'd0, rowstream_tinystories_prompt_token};
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

  wire [31:0] bar_awaddr;
  wire bar_awvalid;
  wire bar_awready;
  wire [31:0] bar_wdata;
  wire [3:0] bar_wstrb;
  wire bar_wvalid;
  wire bar_wready;
  wire [1:0] bar_bresp;
  wire bar_bvalid;
  wire bar_bready;
  wire [31:0] bar_araddr;
  wire bar_arvalid;
  wire bar_arready;
  wire [31:0] bar_rdata;
  wire [1:0] bar_rresp;
  wire bar_rvalid;
  wire bar_rready;
  wire replay_cyc, replay_stb, replay_we, replay_accept, replay_ack, replay_err;
  wire selected_compiler_accept, selected_compiler_ack, selected_compiler_err;
  wire [127:0] selected_compiler_rdata;
  wire [24:0] replay_addr;
  wire [15:0] replay_sel;
  wire [127:0] replay_rdata;
  wire compiler_accel_cyc, compiler_accel_stb, compiler_accel_we;
  wire [24:0] compiler_accel_addr;
  wire [15:0] compiler_accel_sel;
  wire compiler_accel_accept, compiler_accel_ack, compiler_accel_err;
  wire [127:0] compiler_accel_rdata;
  // Preserve the original row-domain-ready synchronizer. Keep local PCIe BAR
  // reset independent of DDR, and request a cross-domain flush only after the
  // row clock/reset domain has demonstrably become live.
  (* ASYNC_REG = "TRUE" *) reg [1:0] replay_pcie_init = 2'b00;
  always @(posedge pcie_user_clk or negedge rowstream_rst_n) begin
    if (!rowstream_rst_n) replay_pcie_init <= 2'b00;
    else replay_pcie_init <= {replay_pcie_init[0], 1'b1};
  end
  (* keep_hierarchy = "yes" *) compiler_ddr3_trace_replay_bridge #(
    .ENABLE_TRACE_CSR(ENABLE_TRACE_REPLAY_CSR)
  ) replay_bridge (
    .pcie_clk(pcie_user_clk), .pcie_reset(!pcie_user_cfg_rst_n),
    .pcie_abort(pcie_user_reset && replay_pcie_init[1]),
    .clk(rowstream_clk), .reset(!rowstream_rst_n), .calib_complete(rowstream_calib_complete),
    .wb_cyc(replay_cyc), .wb_stb(replay_stb), .wb_we(replay_we), .wb_addr(replay_addr),
    .wb_sel(replay_sel), .wb_stall(!selected_compiler_accept), .wb_ack(selected_compiler_ack),
    .wb_err(selected_compiler_err), .wb_rdata(selected_compiler_rdata),
    .s_axi_awaddr(bar_awaddr), .l_axi_awaddr(s_axi_awaddr),
    .s_axi_awvalid(bar_awvalid), .l_axi_awvalid(s_axi_awvalid),
    .s_axi_awready(bar_awready), .l_axi_awready(s_axi_awready),
    .s_axi_wdata(bar_wdata), .l_axi_wdata(s_axi_wdata),
    .s_axi_wstrb(bar_wstrb), .l_axi_wstrb(s_axi_wstrb),
    .s_axi_wvalid(bar_wvalid), .l_axi_wvalid(s_axi_wvalid),
    .s_axi_wready(bar_wready), .l_axi_wready(s_axi_wready),
    .s_axi_bresp(bar_bresp), .l_axi_bresp(s_axi_bresp),
    .s_axi_bvalid(bar_bvalid), .l_axi_bvalid(s_axi_bvalid),
    .s_axi_bready(bar_bready), .l_axi_bready(s_axi_bready),
    .s_axi_araddr(bar_araddr), .l_axi_araddr(s_axi_araddr),
    .s_axi_arvalid(bar_arvalid), .l_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(bar_arready), .l_axi_arready(s_axi_arready),
    .s_axi_rdata(bar_rdata), .l_axi_rdata(s_axi_rdata),
    .s_axi_rresp(bar_rresp), .l_axi_rresp(s_axi_rresp),
    .s_axi_rvalid(bar_rvalid), .l_axi_rvalid(s_axi_rvalid),
    .s_axi_rready(bar_rready), .l_axi_rready(s_axi_rready)
  );

  (* keep_hierarchy = "yes" *) pcie_7x_top_aximm #(
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
    .task6_s_axi_awaddr_o(bar_awaddr),
    .task6_s_axi_awvalid_o(bar_awvalid),
    .task6_s_axi_awready_i(bar_awready),
    .task6_s_axi_wdata_o(bar_wdata),
    .task6_s_axi_wstrb_o(bar_wstrb),
    .task6_s_axi_wvalid_o(bar_wvalid),
    .task6_s_axi_wready_i(bar_wready),
    .task6_s_axi_bresp_i(bar_bresp),
    .task6_s_axi_bvalid_i(bar_bvalid),
    .task6_s_axi_bready_o(bar_bready),
    .task6_s_axi_araddr_o(bar_araddr),
    .task6_s_axi_arvalid_o(bar_arvalid),
    .task6_s_axi_arready_i(bar_arready),
    .task6_s_axi_rdata_i(bar_rdata),
    .task6_s_axi_rvalid_i(bar_rvalid),
    .task6_s_axi_rready_o(bar_rready),
    .task6_s_axi_rresp_i(bar_rresp)
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
    ,.rowstream_tinystories_prompt_ready_i(ENABLE_COMPILER_ACCELERATOR ? compiler_prompt_ready : rowstream_tinystories_prompt_ready)
    ,.rowstream_tinystories_busy_i(ENABLE_COMPILER_ACCELERATOR ? compiler_busy : rowstream_tinystories_busy)
    ,.rowstream_tinystories_error_i(ENABLE_COMPILER_ACCELERATOR ? compiler_error : rowstream_tinystories_error)
    ,.rowstream_tinystories_error_code_i(ENABLE_COMPILER_ACCELERATOR ? compiler_error_code : rowstream_tinystories_error_code)
    ,.rowstream_tinystories_debug_i(ENABLE_COMPILER_ACCELERATOR ? compiler_debug_status[31:0] : rowstream_tinystories_debug[31:0])
    ,.rowstream_tinystories_bridge_error_i(rowstream_tinystories_bridge_error)
    ,.rowstream_tinystories_requests_i(ENABLE_COMPILER_ACCELERATOR ? compiler_request_count : rowstream_tinystories_requests)
    ,.rowstream_tinystories_cache_hits_i(rowstream_tinystories_cache_hits)
    ,.rowstream_tinystories_cache_misses_i(rowstream_tinystories_cache_misses)
    ,.rowstream_tinystories_stall_cycles_i(rowstream_tinystories_stall_cycles)
    ,.rowstream_tinystories_token_valid_i(ENABLE_COMPILER_ACCELERATOR ? compiler_token_valid : rowstream_tinystories_token_valid)
    ,.rowstream_tinystories_token_ready_o(ingress_tinystories_token_ready)
    ,.rowstream_tinystories_token_id_i(ENABLE_COMPILER_ACCELERATOR ? compiler_token_id : rowstream_tinystories_token_id)
`endif
  );

`ifdef TASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS
  // The ingress has one token-ready output.  Route it explicitly to the
  // selected consumer; connecting an output port to a ternary expression
  // leaves the compiler-side net undriven in Yosys.
  assign compiler_token_ready = ENABLE_COMPILER_ACCELERATOR ? ingress_tinystories_token_ready : 1'b0;
  assign rowstream_tinystories_token_ready = ENABLE_COMPILER_ACCELERATOR ? 1'b0 : ingress_tinystories_token_ready;
`endif

  // The physical rowstream owner mux has one accelerator slot.  In compiler
  // mode it services the generated accelerator; otherwise it services the
  // diagnostic trace replayer.  Both consumers observe the same registered
  // response, while the inactive requester remains quiescent.
  assign compiler_accel_accept = selected_compiler_accept;
  assign compiler_accel_ack = selected_compiler_ack;
  assign compiler_accel_err = selected_compiler_err;
  assign compiler_accel_rdata = selected_compiler_rdata;
  assign replay_accept = selected_compiler_accept;
  assign replay_ack = selected_compiler_ack;
  assign replay_err = selected_compiler_err;
  assign replay_rdata = selected_compiler_rdata;

`ifdef TASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS
  generate if (ENABLE_COMPILER_ACCELERATOR) begin : gen_compiler_command_adapter
    if (ENABLE_COMPILER_GENERATED_RC) begin : gen_compiler_generated_rc
      // This instance is the generated pipeline artifact, not a handwritten
      // compute replacement.  The surrounding top supplies only reset,
      // prompt/token framing, and the validated DDR3 Wishbone transport.
      tinystories_integer_rc_wb_top compiler_generated_rc (
        .clk(rowstream_clk), .reset(!rowstream_rst_n),
        .go(rowstream_tinystories_start), .token_data(rc_token_data),
        .done(rc_done),
        .wb_cyc(rc_wb_cyc), .wb_stb(rc_wb_stb), .wb_addr(rc_wb_addr),
        .wb_sel(rc_wb_sel), .wb_accept(compiler_accel_accept),
        .wb_ack(compiler_accel_ack), .wb_err(compiler_accel_err),
        .wb_rdata(compiler_accel_rdata),
        .result0(rc_result0), .result1(rc_result1));
      assign compiler_prompt_ready = 1'b1;
      assign compiler_token_valid = rc_done;
      assign compiler_token_id = {rc_result1, rc_result0};
      // The generated RC currently exposes completion rather than a separate
      // busy signal.  Keep this diagnostic shell quiescent between commands;
      // a production autoregressive wrapper must add an explicit busy/ready
      // contract before board acceptance.
      assign compiler_busy = 1'b0;
      assign compiler_error = compiler_accel_err;
      assign compiler_error_code = compiler_accel_err ? 8'h01 : 8'h00;
      assign compiler_request_count = 32'd0;
      assign compiler_debug_status = 63'd0;
      assign compiler_accel_cyc = rc_wb_cyc;
      assign compiler_accel_stb = rc_wb_stb;
      assign compiler_accel_we = 1'b0;
      assign compiler_accel_addr = rc_wb_addr[24:0];
      assign compiler_accel_sel = rc_wb_sel;
    end else begin : gen_legacy_command_adapter
      tinystories_1m_ddr3_command_adapter compiler_command_adapter (
        .clk(rowstream_clk), .reset(!rowstream_rst_n),
        .clear(rowstream_tinystories_clear),
        .prompt_valid(rowstream_tinystories_prompt),
        .prompt_ready(compiler_prompt_ready),
        .prompt_token(rowstream_tinystories_prompt_token),
        .start(rowstream_tinystories_start),
        .token_valid(compiler_token_valid), .token_ready(compiler_token_ready),
        .token_id(compiler_token_id), .busy(compiler_busy),
        .error(compiler_error), .error_code(compiler_error_code),
        .request_count(compiler_request_count),
        .wb_cyc(compiler_accel_cyc), .wb_stb(compiler_accel_stb),
        .wb_we(compiler_accel_we), .wb_addr(compiler_accel_addr),
        .wb_sel(compiler_accel_sel), .wb_accept(compiler_accel_accept),
        .wb_ack(compiler_accel_ack), .wb_err(compiler_accel_err),
        .wb_rdata(compiler_accel_rdata));
      assign compiler_debug_status = 63'd0;
    end
  end else begin : gen_no_compiler_command_adapter
    assign compiler_prompt_ready = 1'b0;
    assign compiler_token_valid = 1'b0;
    assign compiler_token_id = 16'd0;
    assign compiler_busy = 1'b0;
    assign compiler_error = 1'b0;
    assign compiler_error_code = 8'd0;
    assign compiler_request_count = 32'd0;
    assign compiler_debug_status = 63'd0;
    assign compiler_accel_cyc = 1'b0;
    assign compiler_accel_stb = 1'b0;
    assign compiler_accel_we = 1'b0;
    assign compiler_accel_addr = 25'd0;
    assign compiler_accel_sel = 16'd0;
  end endgenerate
`else
  assign compiler_accel_cyc = 1'b0;
  assign compiler_accel_stb = 1'b0;
  assign compiler_accel_we = 1'b0;
  assign compiler_accel_addr = 25'd0;
  assign compiler_accel_sel = 16'd0;
`endif

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

  // Keep the validated PCIe/UberDDR3 transport as a staged synthesis
  // boundary.  Re-lowering this source closure together with the compiler
  // core is the measured PROC_MUX timebox; the boundary does not alter any
  // transport signal or timing parameter.
  (* keep_hierarchy = "yes" *) task6_ypcb_uberddr3_bist_rowstream_loader_top #(
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
    ,.TINYSTORIES_ENABLE_COMPILER_DDR3(1'b1)
  ) rowstream_ddr3 (
    .compiler_wb_cyc_i(ENABLE_COMPILER_ACCELERATOR ? compiler_accel_cyc : replay_cyc),
    .compiler_wb_stb_i(ENABLE_COMPILER_ACCELERATOR ? compiler_accel_stb : replay_stb),
    .compiler_wb_we_i(ENABLE_COMPILER_ACCELERATOR ? compiler_accel_we : replay_we),
    .compiler_wb_addr_i(ENABLE_COMPILER_ACCELERATOR ? compiler_accel_addr : replay_addr),
    .compiler_wb_data_i(128'd0),
    .compiler_wb_sel_i(ENABLE_COMPILER_ACCELERATOR ? compiler_accel_sel : replay_sel),
    .compiler_wb_accept_o(selected_compiler_accept),
    .compiler_wb_ack_o(selected_compiler_ack),
    .compiler_wb_err_o(selected_compiler_err),
    .compiler_wb_rdata_o(selected_compiler_rdata),
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

// Bundled-data request/response CDC. Payloads stay stable from request toggle
// until acknowledged; two ASYNC_REG flops synchronize each toggle. One operation
// in flight; AW/W are captured independently and B/R are retained independently.
// Physical pending responses survive diagnostic aborts. A subsequent CLEAR is
// held until the pending response drains; no response can leak to a new run.
module compiler_ddr3_trace_replay_bridge #(
  parameter bit ENABLE_TRACE_CSR = 1'b1
) (
  input wire pcie_clk, pcie_reset, pcie_abort,
  input wire clk, reset, calib_complete,
  input wire [31:0] s_axi_awaddr,
  input wire s_axi_awvalid,
  output wire s_axi_awready,
  input wire [31:0] s_axi_wdata,
  input wire [3:0] s_axi_wstrb,
  input wire s_axi_wvalid,
  output wire s_axi_wready,
  output wire [1:0] s_axi_bresp,
  output wire s_axi_bvalid,
  input wire s_axi_bready,
  input wire [31:0] s_axi_araddr,
  input wire s_axi_arvalid,
  output wire s_axi_arready,
  output wire [31:0] s_axi_rdata,
  output wire [1:0] s_axi_rresp,
  output wire s_axi_rvalid,
  input wire s_axi_rready,
  output wire [31:0] l_axi_awaddr,
  output wire l_axi_awvalid,
  input wire l_axi_awready,
  output wire [31:0] l_axi_wdata,
  output wire [3:0] l_axi_wstrb,
  output wire l_axi_wvalid,
  input wire l_axi_wready,
  input wire [1:0] l_axi_bresp,
  input wire l_axi_bvalid,
  output wire l_axi_bready,
  output wire [31:0] l_axi_araddr,
  output wire l_axi_arvalid,
  input wire l_axi_arready,
  input wire [31:0] l_axi_rdata,
  input wire [1:0] l_axi_rresp,
  input wire l_axi_rvalid,
  output wire l_axi_rready,
  output wire wb_cyc, wb_stb, wb_we,
  output wire [24:0] wb_addr,
  output wire [15:0] wb_sel,
  input wire wb_stall, wb_ack, wb_err,
  input wire [127:0] wb_rdata
);
  reg aw_hold, w_hold, ar_hold;
  reg [31:0] awaddr, wdata, araddr;
  reg [3:0] wstrb;
  reg bvalid, rvalid;
  reg [1:0] bresp, rresp;
  reg [31:0] rdata;
  // Four-phase mailbox flush. A runtime PCIe reset discards the local AXI
  // transport immediately, then quarantines it until the row domain has
  // cleared its transport and acknowledged both assertion and deassertion.
  // This also catches a reset pulse shorter than a complete CDC round trip.
  reg [1:0] flush_state; // 0 running, 1 request flush, 2 wait for ack low
  reg flush_ack;
  (* ASYNC_REG = "TRUE" *) reg flush_ack_meta, flush_ack_sync;
  (* ASYNC_REG = "TRUE" *) reg flush_meta, flush_sync;
  wire transport_reset=pcie_reset || pcie_abort || flush_state!=0;
  always @(posedge pcie_clk) begin
    if(pcie_reset) begin
      // The PCIe-domain state is reset locally.  Start a cross-domain flush
      // later through pcie_abort only if the row clock is actually available;
      // otherwise waiting for flush_ack would permanently deadlock BAR reads.
      flush_state<=0; flush_ack_meta<=0; flush_ack_sync<=0;
    end else begin
      flush_ack_meta<=flush_ack; flush_ack_sync<=flush_ack_meta;
      // A reset during an existing flush is already covered. Do not restart
      // phase 2 against a still-high acknowledgement from phase 1.
      if(pcie_abort) begin
        if(flush_state==0) flush_state<=1;
      end
      else case(flush_state)
        1: if(flush_ack_sync) flush_state<=2;
        2: if(!flush_ack_sync) flush_state<=0;
        default: flush_state<=0;
      endcase
    end
  end
  always @(posedge clk) begin
    if(reset) begin flush_meta<=0; flush_sync<=0; flush_ack<=0; end
    else begin
      flush_meta<=flush_state==1; flush_sync<=flush_meta; flush_ack<=flush_sync;
    end
  end
  assign s_axi_awready=!transport_reset && !aw_hold && !bvalid;
  assign s_axi_wready=!transport_reset && !w_hold && !bvalid;
  assign s_axi_arready=!transport_reset && !ar_hold && !rvalid;
  assign s_axi_bvalid=bvalid && !transport_reset;
  assign s_axi_bresp=bresp;
  assign s_axi_rvalid=rvalid && !transport_reset;
  assign s_axi_rresp=rresp;
  assign s_axi_rdata=rdata;
  // 0 idle, 1 loader write, 2 loader read, 3 diagnostic mailbox.
  reg [1:0] pstate;
  reg aw_sent, w_sent, ar_sent;
  reg req_toggle, req_write;
  reg [31:0] req_addr, req_data;
  reg [3:0] req_strb;
  reg response_toggle;
  reg [31:0] response_data;
  reg [1:0] response_code;
  (* ASYNC_REG = "TRUE" *) reg resp_meta, resp_sync;
  // axis_pcie_to_al_us preserves the absolute host address. Decode this
  // 4-KiB BAR by aperture offset, matching the legacy loader CSR behavior.
  wire [11:0] aw_offset = awaddr[11:0];
  wire [11:0] ar_offset = araddr[11:0];
  assign l_axi_awaddr=awaddr;
  assign l_axi_wdata=wdata;
  assign l_axi_wstrb=wstrb;
  assign l_axi_awvalid=!transport_reset && pstate==1 && !aw_sent;
  assign l_axi_wvalid=!transport_reset && pstate==1 && !w_sent;
  assign l_axi_bready=!transport_reset && pstate==1;
  assign l_axi_araddr=araddr;
  assign l_axi_arvalid=!transport_reset && pstate==2 && !ar_sent;
  assign l_axi_rready=!transport_reset && pstate==2;
  always @(posedge pcie_clk) begin
    if(transport_reset) begin
      aw_hold<=0; w_hold<=0; ar_hold<=0; bvalid<=0; rvalid<=0;
      awaddr<=0; wdata<=0; araddr<=0; wstrb<=0; bresp<=0; rresp<=0; rdata<=0;
      pstate<=0; aw_sent<=0; w_sent<=0; ar_sent<=0;
      // Keep the bundled payload stable until row-side cancellation is
      // acknowledged. Only then rebase both mailbox toggles to zero.
      if(pcie_reset || (flush_state==1 && flush_ack_sync) || flush_state==2) begin
        req_toggle<=0; req_write<=0; req_addr<=0; req_data<=0; req_strb<=0;
      end
      resp_meta<=0; resp_sync<=0;
    end else begin
      resp_meta<=response_toggle; resp_sync<=resp_meta;
      if(s_axi_awvalid && s_axi_awready) begin aw_hold<=1; awaddr<=s_axi_awaddr; end
      if(s_axi_wvalid && s_axi_wready) begin w_hold<=1; wdata<=s_axi_wdata; wstrb<=s_axi_wstrb; end
      if(s_axi_arvalid && s_axi_arready) begin ar_hold<=1; araddr<=s_axi_araddr; end
      if(bvalid && s_axi_bready) bvalid<=0;
      if(rvalid && s_axi_rready) rvalid<=0;
      case(pstate)
        0: begin
          aw_sent<=0; w_sent<=0; ar_sent<=0;
          if(aw_hold && w_hold && !bvalid) begin
            if(aw_offset>=12'h900 && aw_offset<12'h980) begin
              if (ENABLE_TRACE_CSR) begin
                req_write<=1; req_addr<={20'd0,aw_offset}; req_data<=wdata; req_strb<=wstrb;
                req_toggle<=!req_toggle; pstate<=3;
              end else begin
                // Trace offsets are intentionally unavailable in production;
                // complete the AXI request deterministically with DECERR.
                bvalid<=1; bresp<=2'b11; aw_hold<=0; w_hold<=0; pstate<=0;
              end
            end else pstate<=1;
          end else if(ar_hold && !rvalid) begin
            if(ar_offset>=12'h900 && ar_offset<12'h980) begin
              if (ENABLE_TRACE_CSR) begin
                req_write<=0; req_addr<={20'd0,ar_offset}; req_data<=0; req_strb<=0;
                req_toggle<=!req_toggle; pstate<=3;
              end else begin
                rvalid<=1; rresp<=2'b11; rdata<=32'd0; ar_hold<=0; pstate<=0;
              end
            end else pstate<=2;
          end
        end
        1: begin
          if(l_axi_awvalid && l_axi_awready) aw_sent<=1;
          if(l_axi_wvalid && l_axi_wready) w_sent<=1;
          if(l_axi_bvalid) begin
            bvalid<=1; bresp<=l_axi_bresp; aw_hold<=0; w_hold<=0; pstate<=0;
          end
        end
        2: begin
          if(l_axi_arvalid && l_axi_arready) ar_sent<=1;
          if(l_axi_rvalid) begin
            rvalid<=1; rresp<=l_axi_rresp; rdata<=l_axi_rdata; ar_hold<=0; pstate<=0;
          end
        end
        3: if(resp_sync==req_toggle) begin
          if(req_write) begin
            bvalid<=1; bresp<=response_code; aw_hold<=0; w_hold<=0;
          end else begin
            rvalid<=1; rresp<=response_code; rdata<=response_data; ar_hold<=0;
          end
          pstate<=0;
        end
      endcase
    end
  end
  (* ASYNC_REG = "TRUE" *) reg req_meta, req_sync, abort_meta, abort_sync;
  reg [1:0] dstate;
  reg d_aw_sent, d_w_sent, d_ar_sent;
  wire d_awready, d_wready, d_bvalid, d_arready, d_rvalid;
  wire [1:0] d_bresp, d_rresp;
  wire [31:0] d_rdata;
  wire replay_active, core_cyc, core_stb, core_we;
  wire [31:0] core_addr;
  wire [15:0] core_sel;
  reg pending;
  wire invalid_address=|core_addr[31:25];
  wire physical_accept=wb_cyc && wb_stb && !wb_stall;
  wire physical_response=wb_ack || wb_err;
  // Register the external-memory response bundle before it re-enters the
  // replay CSR state machine.  The three signals must cross together: a
  // response is accepted one controller cycle later, with the same data and
  // error code.  This preserves ordered trace semantics while breaking the
  // measured CSR-state -> compiler-rdata critical path.
  reg wb_ack_q, wb_err_q;
  reg [127:0] wb_rdata_q;
  always @(posedge clk) begin
    if (reset) begin
      wb_ack_q <= 1'b0;
      wb_err_q <= 1'b0;
      wb_rdata_q <= 128'd0;
    end else begin
      wb_ack_q <= wb_ack;
      wb_err_q <= wb_err;
      if (wb_ack || wb_err)
        wb_rdata_q <= wb_rdata;
    end
  end
  // Keep the accelerator CYC high through FIFO starvation and late responses.
  // The unmodified production owner mux waits for a host CYC already in flight.
  assign wb_cyc=replay_active || core_cyc || pending;
  assign wb_stb=core_stb && !invalid_address && !pending;
  assign wb_we=core_we;
  assign wb_addr=core_addr[24:0];
  assign wb_sel=core_sel;
  always @(posedge clk) begin
    if(reset) pending<=0;
    else if(pending && physical_response) pending<=0;
    else if(physical_accept) pending<=!physical_response;
  end
  compiler_ddr3_trace_replay_csr #(
    .ENABLE_TRACE_CSR(ENABLE_TRACE_CSR)
  ) csr (
    .clk(clk), .reset(reset), .transport_reset(flush_sync),
    .replay_reset(abort_sync || flush_sync), .calib_complete(calib_complete),
    .s_axi_awaddr(req_addr), .s_axi_awvalid(dstate==1 && !d_aw_sent), .s_axi_awready(d_awready),
    .s_axi_wdata(req_data), .s_axi_wstrb(req_strb),
    .s_axi_wvalid(dstate==1 && !d_w_sent), .s_axi_wready(d_wready),
    .s_axi_bresp(d_bresp), .s_axi_bvalid(d_bvalid), .s_axi_bready(dstate==1),
    .s_axi_araddr(req_addr), .s_axi_arvalid(dstate==2 && !d_ar_sent), .s_axi_arready(d_arready),
    .s_axi_rdata(d_rdata), .s_axi_rvalid(d_rvalid), .s_axi_rready(dstate==2), .s_axi_rresp(d_rresp),
    .replay_active(replay_active), .wb_cyc(core_cyc), .wb_stb(core_stb), .wb_we(core_we),
    .wb_addr(core_addr), .wb_sel(core_sel),
    .wb_stall(invalid_address ? 1'b0 : (wb_stall || pending)),
    .wb_ack(wb_ack_q),
    .wb_err(wb_err_q || (core_cyc && core_stb && invalid_address)),
    .wb_rdata(wb_rdata_q)
  );
  always @(posedge clk) begin
    if(reset) begin
      req_meta<=0; req_sync<=0; abort_meta<=0; abort_sync<=0;
      response_toggle<=0; response_code<=0; response_data<=0;
      dstate<=0; d_aw_sent<=0; d_w_sent<=0; d_ar_sent<=0;
    end else begin
      req_meta<=req_toggle; req_sync<=req_meta; abort_meta<=pcie_abort; abort_sync<=abort_meta;
      if(flush_sync) begin
        req_meta<=0; req_sync<=0;
        response_toggle<=0; response_code<=0; response_data<=0;
        dstate<=0; d_aw_sent<=0; d_w_sent<=0; d_ar_sent<=0;
      end else case(dstate)
        0: begin
          d_aw_sent<=0; d_w_sent<=0; d_ar_sent<=0;
          if(req_sync!=response_toggle && !(req_write && req_addr==32'h908 && pending && !replay_active))
            dstate<=req_write ? 1 : 2;
        end
        1: begin
          if(!d_aw_sent && d_awready) d_aw_sent<=1;
          if(!d_w_sent && d_wready) d_w_sent<=1;
          if(d_bvalid) begin
            response_code<=d_bresp; response_data<=0; response_toggle<=req_sync; dstate<=0;
          end
        end
        2: begin
          if(!d_ar_sent && d_arready) d_ar_sent<=1;
          if(d_rvalid) begin
            response_code<=d_rresp; response_data<=d_rdata; response_toggle<=req_sync; dstate<=0;
          end
        end
      endcase
    end
  end
endmodule
