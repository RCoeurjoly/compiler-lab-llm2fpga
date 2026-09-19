`timescale 1ns/1ps
// SPDX-License-Identifier: MIT

`default_nettype none

module task6_pcie_axil_rowstream_loader_ingress_cdc #(
    parameter integer COMMAND_WIDTH = 208,
    parameter integer COMMAND_DATA_LSB = 80,
    parameter integer M2_INPUT_PCIE7X_ROR64_COMPENSATE = 0
) (
    input wire pcie_clk,
    input wire pcie_rst_n,
    input wire rowstream_clk,
    input wire rowstream_rst_n,

    input wire [31:0] s_axi_awaddr,
    input wire        s_axi_awvalid,
    output wire       s_axi_awready,
    input wire [31:0] s_axi_wdata,
    input wire [3:0]  s_axi_wstrb,
    input wire        s_axi_wvalid,
    output wire       s_axi_wready,
    output wire [1:0] s_axi_bresp,
    output wire       s_axi_bvalid,
    input wire        s_axi_bready,
    input wire [31:0] s_axi_araddr,
    input wire        s_axi_arvalid,
    output wire       s_axi_arready,
    output wire [31:0] s_axi_rdata,
    output wire       s_axi_rvalid,
    input wire        s_axi_rready,
    output wire [1:0] s_axi_rresp,

    output reg [COMMAND_WIDTH - 1:0] rowstream_command_payload_o,
    output reg                       rowstream_command_event_o,
    output reg                       rowstream_status_clear_o,

    input wire        rowstream_calib_complete_i,
    input wire        rowstream_boot_done_i,
    input wire [31:0] rowstream_ddr_debug1_i,
    input wire        rowstream_loader_done_i,
    input wire        rowstream_loader_error_i,
    input wire        rowstream_loader_last_accepted_i,
    input wire        rowstream_loader_last_magic_ok_i,
    input wire [7:0]  rowstream_loader_last_opcode_i,
    input wire [1:0]  rowstream_loader_last_chunk_i,
    input wire [31:0] rowstream_loader_command_payload_addr_i,
    input wire [31:0] rowstream_loader_wait_cycles_i,
    input wire [511:0] rowstream_loader_read_data_i,

    output reg [511:0] rowstream_top1_hidden_vector_o,
    output reg         rowstream_top1_start_o,
    output reg         rowstream_top1_status_clear_o,
    input wire         rowstream_top1_busy_i,
    input wire         rowstream_top1_done_i,
    input wire         rowstream_top1_error_i,
    input wire [31:0]  rowstream_top1_token_i,
    input wire [31:0]  rowstream_top1_score_q024_i,
    input wire [31:0]  rowstream_top1_rows_scanned_i,
    input wire [31:0]  rowstream_top1_cycle_count_i,
    input wire [31:0]  rowstream_top1_debug_status_i,
    input wire [31:0]  rowstream_top1_debug_reader_addr_i,
    input wire [31:0]  rowstream_top1_debug_wb_ack_count_i,
    input wire [31:0]  rowstream_top1_debug_wb_err_count_i,
    input wire [31:0]  rowstream_top1_debug_packet_wb_write_ack_count_i,
    input wire [31:0]  rowstream_top1_debug_packet_wb_read_ack_count_i,

    input wire         rowstream_mlp_selftest_present_i,
    input wire [31:0]  rowstream_mlp_selftest_status_i,
    input wire [31:0]  rowstream_mlp_selftest_cycle_count_i,
    input wire [31:0]  rowstream_mlp_selftest_fail_detail_i,
    input wire [31:0]  rowstream_mlp_selftest_fail_values_i,
    input wire [31:0]  rowstream_mlp_selftest_first_add_sample_i,
    input wire [31:0]  rowstream_mlp_selftest_first_requant_sample_i,
    input wire [31:0]  rowstream_mlp_selftest_requant_debug0_i,
    input wire [31:0]  rowstream_mlp_selftest_requant_debug1_i,
    output reg [31:0]  rowstream_mlp_selftest_debug_select_o,

    output reg [511:0] rowstream_mlp_accel_activation_vector_o,
    output reg [511:0] rowstream_mlp_accel_residual_vector_o,
    output reg         rowstream_mlp_accel_start_o,
    output reg         rowstream_mlp_accel_clear_o,
    input wire [31:0]  rowstream_mlp_accel_status_i,
    input wire [31:0]  rowstream_mlp_accel_cycle_count_i,
    input wire [31:0]  rowstream_mlp_accel_output_checksum_i,
    input wire [31:0]  rowstream_mlp_accel_output_sample0_i,
    input wire [31:0]  rowstream_mlp_accel_output_sample1_i,
    input wire [511:0] rowstream_mlp_accel_output_vector_i,

    output reg [511:0] rowstream_m2_full_block_input_vector_o,
    output reg [511:0] rowstream_m2_full_block_residual_vector_o,
    output reg         rowstream_m2_full_block_start_o,
    output reg         rowstream_m2_full_block_clear_o,
    input wire [31:0]  rowstream_m2_full_block_status_i,
    input wire [31:0]  rowstream_m2_full_block_cycle_count_i,
    input wire [31:0]  rowstream_m2_full_block_output_checksum_i,
    input wire [31:0]  rowstream_m2_full_block_output_sample0_i,
    input wire [31:0]  rowstream_m2_full_block_output_sample1_i,
    input wire [31:0]  rowstream_m2_full_block_output_count_i,
    input wire [31:0]  rowstream_m2_full_block_debug_i,
    input wire [31:0]  rowstream_m2_full_block_debug1_i,
    input wire [31:0]  rowstream_m2_full_block_debug2_i,
    input wire [31:0]  rowstream_m2_full_block_debug3_i,
    input wire [31:0]  rowstream_m2_full_block_provenance_i,
    input wire [127:0] rowstream_m2_full_block_output_hash_i,
    input wire [511:0] rowstream_m2_full_block_output_vector_i,

    output reg [15:0]  rowstream_tinystories_prompt_token_o,
    output reg [7:0]   rowstream_tinystories_requested_tokens_o,
    output reg [31:0]  rowstream_tinystories_package_tag_o,
    output reg         rowstream_tinystories_prompt_o,
    output reg         rowstream_tinystories_start_o,
    output reg         rowstream_tinystories_clear_o,
    input wire         rowstream_tinystories_prompt_ready_i,
    input wire         rowstream_tinystories_busy_i,
    input wire         rowstream_tinystories_error_i,
    input wire [7:0]   rowstream_tinystories_error_code_i,
    input wire [31:0]  rowstream_tinystories_debug_i,
    input wire         rowstream_tinystories_bridge_error_i,
    input wire [31:0]  rowstream_tinystories_requests_i,
    input wire [31:0]  rowstream_tinystories_cache_hits_i,
    input wire [31:0]  rowstream_tinystories_cache_misses_i,
    input wire [31:0]  rowstream_tinystories_stall_cycles_i,
    input wire         rowstream_tinystories_token_valid_i,
    output wire        rowstream_tinystories_token_ready_o,
    input wire [15:0]  rowstream_tinystories_token_id_i
);
    wire [COMMAND_WIDTH - 1:0] pcie_command_payload;
    wire pcie_command_event;
    wire pcie_status_clear;
    wire [511:0] pcie_top1_hidden_vector;
    wire pcie_top1_start;
    wire pcie_top1_status_clear;
    wire [511:0] pcie_mlp_accel_activation_vector;
    wire [511:0] pcie_mlp_accel_residual_vector;
    wire pcie_mlp_accel_start;
    wire pcie_mlp_accel_clear;
    wire [31:0] pcie_mlp_selftest_debug_select;
    wire [511:0] pcie_m2_full_block_input_vector;
    wire [511:0] pcie_m2_full_block_residual_vector;
    wire pcie_m2_full_block_start;
    wire pcie_m2_full_block_clear;
    wire [15:0] pcie_tinystories_prompt_token;
    wire [7:0] pcie_tinystories_requested_tokens;
    wire [31:0] pcie_tinystories_package_tag;
    wire pcie_tinystories_prompt;
    wire pcie_tinystories_start;
    wire pcie_tinystories_clear;
    wire [5:0] pcie_tinystories_token_count;
    wire pcie_tinystories_token_overflow;
    wire [511:0] pcie_tinystories_token_vector;

    reg req_toggle_pcie_q;
    reg clear_toggle_pcie_q;
    reg top1_start_toggle_pcie_q;
    reg top1_clear_toggle_pcie_q;
    reg mlp_accel_start_toggle_pcie_q;
    reg mlp_accel_clear_toggle_pcie_q;
    reg m2_full_block_start_toggle_pcie_q;
    reg m2_full_block_clear_toggle_pcie_q;
    // Keep the command format unchanged, but split the CDC-held payload into
    // four independently placed banks.  The previous monolithic 208-bit
    // cross-domain bundle was the dominant pcie_user_clk -> rowstream_clk
    // integration cone in the fixed-profile timing report.
    localparam integer PAYLOAD_CHUNK_WIDTH = COMMAND_WIDTH / 4;
    reg [PAYLOAD_CHUNK_WIDTH - 1:0] payload_hold_pcie_q [0:3];
    reg [511:0] top1_hidden_hold_pcie_q;
    reg [511:0] mlp_accel_activation_hold_pcie_q;
    reg [511:0] mlp_accel_residual_hold_pcie_q;
    reg [31:0] mlp_selftest_debug_select_hold_pcie_q;
    reg [511:0] m2_full_block_input_hold_pcie_q;
    reg [511:0] m2_full_block_residual_hold_pcie_q;
    reg tinystories_prompt_toggle_pcie_q;
    reg tinystories_start_toggle_pcie_q;
    reg tinystories_clear_toggle_pcie_q;
    reg [15:0] tinystories_prompt_hold_pcie_q;
    reg [7:0] tinystories_requested_hold_pcie_q;
    reg [31:0] tinystories_package_tag_hold_pcie_q;

    reg [2:0] req_sync_row_q;
    reg req_seen_row_q;
    reg [2:0] clear_sync_row_q;
    reg clear_seen_row_q;
    reg [2:0] top1_start_sync_row_q;
    reg top1_start_seen_row_q;
    reg [2:0] top1_clear_sync_row_q;
    reg top1_clear_seen_row_q;
    reg [2:0] mlp_accel_start_sync_row_q;
    reg mlp_accel_start_seen_row_q;
    reg [2:0] mlp_accel_clear_sync_row_q;
    reg mlp_accel_clear_seen_row_q;
    reg [2:0] m2_full_block_start_sync_row_q;
    reg m2_full_block_start_seen_row_q;
    reg [2:0] m2_full_block_clear_sync_row_q;
    reg m2_full_block_clear_seen_row_q;
    reg [2:0] tinystories_prompt_sync_row_q;
    reg tinystories_prompt_seen_row_q;
    reg [2:0] tinystories_start_sync_row_q;
    reg tinystories_start_seen_row_q;
    reg [2:0] tinystories_clear_sync_row_q;
    reg tinystories_clear_seen_row_q;
    reg [31:0] mlp_selftest_debug_select_sync1_row_q;
    reg [31:0] mlp_selftest_debug_select_sync2_row_q;

    reg [2:0] calib_complete_sync_pcie_q;
    reg [2:0] boot_done_sync_pcie_q;
    reg [2:0] loader_done_sync_pcie_q;
    reg [2:0] loader_error_sync_pcie_q;
    reg [2:0] loader_accepted_sync_pcie_q;
    reg [2:0] rowstream_rst_n_sync_pcie_q;
    reg [2:0] rowstream_heartbeat_sync_pcie_q;
    reg rowstream_heartbeat_last_pcie_q;
    reg [31:0] rowstream_heartbeat_count_pcie_q;
    reg [31:0] rowstream_seen_pcie_q;
    reg [2:0] loader_magic_ok_sync_pcie_q;
    reg [7:0] loader_opcode_pcie_q;
    reg [1:0] loader_chunk_pcie_q;
    reg [31:0] loader_addr_pcie_q;
    reg [31:0] loader_wait_pcie_q;
    // Stage the asynchronous debug bus before reduction/snapshot logic.  The
    // previous direct reduction created a long rowstream timing path.
    reg [31:0] rowstream_ddr_debug1_sample_pcie_q;
    reg [31:0] ddr_debug1_pcie_q;
    reg [511:0] loader_read_data_pcie_q;
    reg [2:0] top1_busy_sync_pcie_q;
    reg [2:0] top1_done_sync_pcie_q;
    reg [2:0] top1_error_sync_pcie_q;
    reg [31:0] top1_token_pcie_q;
    reg [31:0] top1_score_pcie_q;
    reg [31:0] top1_rows_pcie_q;
    reg [31:0] top1_cycles_pcie_q;
    reg [31:0] top1_debug_status_pcie_q;
    reg [31:0] top1_debug_reader_addr_pcie_q;
    reg [31:0] top1_debug_wb_ack_count_pcie_q;
    reg [31:0] top1_debug_wb_err_count_pcie_q;
    reg [31:0] top1_debug_packet_wb_write_ack_count_pcie_q;
    reg [31:0] top1_debug_packet_wb_read_ack_count_pcie_q;
    reg [2:0] mlp_selftest_present_sync_pcie_q;
    reg [31:0] mlp_selftest_status_pcie_q;
    reg [31:0] mlp_selftest_cycle_count_pcie_q;
    reg [31:0] mlp_selftest_fail_detail_pcie_q;
    reg [31:0] mlp_selftest_fail_values_pcie_q;
    reg [31:0] mlp_selftest_first_add_sample_pcie_q;
    reg [31:0] mlp_selftest_first_requant_sample_pcie_q;
    reg [31:0] mlp_selftest_requant_debug0_pcie_q;
    reg [31:0] mlp_selftest_requant_debug1_pcie_q;
    reg [31:0] mlp_accel_status_pcie_q;
    reg [31:0] mlp_accel_cycle_count_pcie_q;
    reg [31:0] mlp_accel_output_checksum_pcie_q;
    reg [31:0] mlp_accel_output_sample0_pcie_q;
    reg [31:0] mlp_accel_output_sample1_pcie_q;
    reg [511:0] mlp_accel_output_vector_pcie_q;
    reg [31:0] m2_full_block_status_pcie_q;
    reg [31:0] m2_full_block_cycle_count_pcie_q;
    reg [31:0] m2_full_block_output_checksum_pcie_q;
    reg [31:0] m2_full_block_output_sample0_pcie_q;
    reg [31:0] m2_full_block_output_sample1_pcie_q;
    reg [31:0] m2_full_block_output_count_pcie_q;
    reg [31:0] m2_full_block_debug_pcie_q;
    reg [31:0] m2_full_block_debug1_pcie_q;
    reg [31:0] m2_full_block_debug2_pcie_q;
    reg [31:0] m2_full_block_debug3_pcie_q;
    reg [31:0] m2_full_block_provenance_pcie_q;
    reg [127:0] m2_full_block_output_hash_pcie_q;
    reg [511:0] m2_full_block_output_vector_pcie_q;
    reg [2:0] tinystories_prompt_ready_sync_pcie_q;
    reg [2:0] tinystories_busy_sync_pcie_q;
    reg [2:0] tinystories_error_sync_pcie_q;
    reg [2:0] tinystories_bridge_error_sync_pcie_q;
    reg [7:0] tinystories_error_code_pcie_q;
    reg [31:0] tinystories_debug_pcie_q;
    reg [31:0] tinystories_requests_pcie_q;
    reg [31:0] tinystories_cache_hits_pcie_q;
    reg [31:0] tinystories_cache_misses_pcie_q;
    reg [31:0] tinystories_stall_cycles_pcie_q;
    reg [31:0] rowstream_clk_counter_q;
    wire rowstream_heartbeat_edge = rowstream_heartbeat_sync_pcie_q[2] ^ rowstream_heartbeat_last_pcie_q;

    task6_tinystories_token_cdc tinystories_token_cdc (
        .rowstream_clk(rowstream_clk),
        .rowstream_rst_n(rowstream_rst_n),
        .pcie_clk(pcie_clk),
        .pcie_rst_n(pcie_rst_n),
        .pcie_start(pcie_tinystories_start),
        .pcie_clear(pcie_tinystories_clear),
        .rowstream_token_valid(rowstream_tinystories_token_valid_i),
        .rowstream_token_ready(rowstream_tinystories_token_ready_o),
        .rowstream_token_id(rowstream_tinystories_token_id_i),
        .pcie_token_count(pcie_tinystories_token_count),
        .pcie_tokens(pcie_tinystories_token_vector),
        .pcie_overflow(pcie_tinystories_token_overflow)
    );

    task6_pcie_axil_rowstream_loader_ingress #(
        .COMMAND_WIDTH(COMMAND_WIDTH),
        .COMMAND_DATA_LSB(COMMAND_DATA_LSB),
        .M2_INPUT_PCIE7X_ROR64_COMPENSATE(M2_INPUT_PCIE7X_ROR64_COMPENSATE)
    ) ingress (
        .clk(pcie_clk),
        .rst_n(pcie_rst_n),
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
        .command_payload_o(pcie_command_payload),
        .command_event_o(pcie_command_event),
        .calib_complete_i(calib_complete_sync_pcie_q[2]),
        .boot_done_i(boot_done_sync_pcie_q[2]),
        .ddr_debug1_i(ddr_debug1_pcie_q),
        .debug_rowstream_heartbeat_count_i(rowstream_heartbeat_count_pcie_q),
        .debug_rowstream_status_i({24'd0, top1_busy_sync_pcie_q[2], loader_error_sync_pcie_q[2], loader_done_sync_pcie_q[2], rowstream_heartbeat_sync_pcie_q[2], boot_done_sync_pcie_q[2], calib_complete_sync_pcie_q[2], rowstream_rst_n_sync_pcie_q[2], pcie_rst_n}),
        .debug_rowstream_seen_i(rowstream_seen_pcie_q),
        .loader_done_i(loader_done_sync_pcie_q[2]),
        .loader_error_i(loader_error_sync_pcie_q[2]),
        .loader_last_accepted_i(loader_accepted_sync_pcie_q[2]),
        .loader_last_magic_ok_i(loader_magic_ok_sync_pcie_q[2]),
        .loader_last_opcode_i(loader_opcode_pcie_q),
        .loader_last_chunk_i(loader_chunk_pcie_q),
        .loader_command_payload_addr_i(loader_addr_pcie_q),
        .loader_wait_cycles_i(loader_wait_pcie_q),
        .loader_read_data_i(loader_read_data_pcie_q),
        .status_clear_pulse_o(pcie_status_clear),
        .top1_hidden_vector_o(pcie_top1_hidden_vector),
        .top1_start_pulse_o(pcie_top1_start),
        .top1_status_clear_pulse_o(pcie_top1_status_clear),
        .top1_busy_i(top1_busy_sync_pcie_q[2]),
        .top1_done_i(top1_done_sync_pcie_q[2]),
        .top1_error_i(top1_error_sync_pcie_q[2]),
        .top1_token_i(top1_token_pcie_q),
        .top1_score_q024_i(top1_score_pcie_q),
        .top1_rows_scanned_i(top1_rows_pcie_q),
        .top1_cycle_count_i(top1_cycles_pcie_q),
        .top1_debug_status_i(top1_debug_status_pcie_q),
        .top1_debug_reader_addr_i(top1_debug_reader_addr_pcie_q),
        .top1_debug_wb_ack_count_i(top1_debug_wb_ack_count_pcie_q),
        .top1_debug_wb_err_count_i(top1_debug_wb_err_count_pcie_q),
        .top1_debug_packet_wb_write_ack_count_i(top1_debug_packet_wb_write_ack_count_pcie_q),
        .top1_debug_packet_wb_read_ack_count_i(top1_debug_packet_wb_read_ack_count_pcie_q),
        .mlp_selftest_present_i(mlp_selftest_present_sync_pcie_q[2]),
        .mlp_selftest_status_i(mlp_selftest_status_pcie_q),
        .mlp_selftest_cycle_count_i(mlp_selftest_cycle_count_pcie_q),
        .mlp_selftest_fail_detail_i(mlp_selftest_fail_detail_pcie_q),
        .mlp_selftest_fail_values_i(mlp_selftest_fail_values_pcie_q),
        .mlp_selftest_first_add_sample_i(mlp_selftest_first_add_sample_pcie_q),
        .mlp_selftest_first_requant_sample_i(mlp_selftest_first_requant_sample_pcie_q),
        .mlp_selftest_requant_debug0_i(mlp_selftest_requant_debug0_pcie_q),
        .mlp_selftest_requant_debug1_i(mlp_selftest_requant_debug1_pcie_q),
        .mlp_selftest_debug_select_o(pcie_mlp_selftest_debug_select),
        .mlp_accel_activation_vector_o(pcie_mlp_accel_activation_vector),
        .mlp_accel_residual_vector_o(pcie_mlp_accel_residual_vector),
        .mlp_accel_start_pulse_o(pcie_mlp_accel_start),
        .mlp_accel_clear_pulse_o(pcie_mlp_accel_clear),
        .mlp_accel_status_i(mlp_accel_status_pcie_q),
        .mlp_accel_cycle_count_i(mlp_accel_cycle_count_pcie_q),
        .mlp_accel_output_checksum_i(mlp_accel_output_checksum_pcie_q),
        .mlp_accel_output_sample0_i(mlp_accel_output_sample0_pcie_q),
        .mlp_accel_output_sample1_i(mlp_accel_output_sample1_pcie_q),
        .mlp_accel_output_vector_i(mlp_accel_output_vector_pcie_q),
        .m2_full_block_input_vector_o(pcie_m2_full_block_input_vector),
        .m2_full_block_residual_vector_o(pcie_m2_full_block_residual_vector),
        .m2_full_block_start_pulse_o(pcie_m2_full_block_start),
        .m2_full_block_clear_pulse_o(pcie_m2_full_block_clear),
        .m2_full_block_status_i(m2_full_block_status_pcie_q),
        .m2_full_block_cycle_count_i(m2_full_block_cycle_count_pcie_q),
        .m2_full_block_output_checksum_i(m2_full_block_output_checksum_pcie_q),
        .m2_full_block_output_sample0_i(m2_full_block_output_sample0_pcie_q),
        .m2_full_block_output_sample1_i(m2_full_block_output_sample1_pcie_q),
        .m2_full_block_output_count_i(m2_full_block_output_count_pcie_q),
        .m2_full_block_debug_i(m2_full_block_debug_pcie_q),
        .m2_full_block_debug1_i(m2_full_block_debug1_pcie_q),
        .m2_full_block_debug2_i(m2_full_block_debug2_pcie_q),
        .m2_full_block_debug3_i(m2_full_block_debug3_pcie_q),
        .m2_full_block_provenance_i(m2_full_block_provenance_pcie_q),
        .m2_full_block_output_hash_i(m2_full_block_output_hash_pcie_q),
        .m2_full_block_output_vector_i(m2_full_block_output_vector_pcie_q),
        .tinystories_prompt_token_o(pcie_tinystories_prompt_token),
        .tinystories_requested_tokens_o(pcie_tinystories_requested_tokens),
        .tinystories_package_tag_o(pcie_tinystories_package_tag),
        .tinystories_prompt_pulse_o(pcie_tinystories_prompt),
        .tinystories_start_pulse_o(pcie_tinystories_start),
        .tinystories_clear_pulse_o(pcie_tinystories_clear),
        .tinystories_prompt_ready_i(tinystories_prompt_ready_sync_pcie_q[2]),
        .tinystories_busy_i(tinystories_busy_sync_pcie_q[2]),
        .tinystories_error_i(tinystories_error_sync_pcie_q[2]),
        .tinystories_error_code_i(tinystories_error_code_pcie_q),
        .tinystories_debug_i(tinystories_debug_pcie_q),
        .tinystories_bridge_error_i(tinystories_bridge_error_sync_pcie_q[2]),
        .tinystories_requests_i(tinystories_requests_pcie_q),
        .tinystories_cache_hits_i(tinystories_cache_hits_pcie_q),
        .tinystories_cache_misses_i(tinystories_cache_misses_pcie_q),
        .tinystories_stall_cycles_i(tinystories_stall_cycles_pcie_q),
        .tinystories_token_count_i(pcie_tinystories_token_count),
        .tinystories_token_overflow_i(pcie_tinystories_token_overflow),
        .tinystories_token_vector_i(pcie_tinystories_token_vector)
    );

    always @(posedge pcie_clk or negedge pcie_rst_n) begin
        if (!pcie_rst_n) begin
            req_toggle_pcie_q <= 1'b0;
            clear_toggle_pcie_q <= 1'b0;
            top1_start_toggle_pcie_q <= 1'b0;
            top1_clear_toggle_pcie_q <= 1'b0;
            mlp_accel_start_toggle_pcie_q <= 1'b0;
            mlp_accel_clear_toggle_pcie_q <= 1'b0;
            m2_full_block_start_toggle_pcie_q <= 1'b0;
            m2_full_block_clear_toggle_pcie_q <= 1'b0;
            payload_hold_pcie_q[0] <= {PAYLOAD_CHUNK_WIDTH{1'b0}};
            payload_hold_pcie_q[1] <= {PAYLOAD_CHUNK_WIDTH{1'b0}};
            payload_hold_pcie_q[2] <= {PAYLOAD_CHUNK_WIDTH{1'b0}};
            payload_hold_pcie_q[3] <= {PAYLOAD_CHUNK_WIDTH{1'b0}};
            top1_hidden_hold_pcie_q <= 512'd0;
            mlp_accel_activation_hold_pcie_q <= 512'd0;
            mlp_accel_residual_hold_pcie_q <= 512'd0;
            mlp_selftest_debug_select_hold_pcie_q <= 32'd0;
            m2_full_block_input_hold_pcie_q <= 512'd0;
            m2_full_block_residual_hold_pcie_q <= 512'd0;
            tinystories_prompt_toggle_pcie_q <= 1'b0;
            tinystories_start_toggle_pcie_q <= 1'b0;
            tinystories_clear_toggle_pcie_q <= 1'b0;
            tinystories_prompt_hold_pcie_q <= 16'd0;
            tinystories_requested_hold_pcie_q <= 8'd16;
            tinystories_package_tag_hold_pcie_q <= 32'd0;
            calib_complete_sync_pcie_q <= 3'd0;
            boot_done_sync_pcie_q <= 3'd0;
            loader_done_sync_pcie_q <= 3'd0;
            loader_error_sync_pcie_q <= 3'd0;
            loader_accepted_sync_pcie_q <= 3'd0;
            rowstream_rst_n_sync_pcie_q <= 3'd0;
            rowstream_heartbeat_sync_pcie_q <= 3'd0;
            rowstream_heartbeat_last_pcie_q <= 1'b0;
            rowstream_heartbeat_count_pcie_q <= 32'd0;
            rowstream_seen_pcie_q <= 32'd0;
            loader_magic_ok_sync_pcie_q <= 3'd0;
            loader_opcode_pcie_q <= 8'd0;
            loader_chunk_pcie_q <= 2'd0;
            loader_addr_pcie_q <= 32'd0;
            loader_wait_pcie_q <= 32'd0;
            rowstream_ddr_debug1_sample_pcie_q <= 32'd0;
            ddr_debug1_pcie_q <= 32'd0;
            loader_read_data_pcie_q <= 512'd0;
            top1_busy_sync_pcie_q <= 3'd0;
            top1_done_sync_pcie_q <= 3'd0;
            top1_error_sync_pcie_q <= 3'd0;
            top1_token_pcie_q <= 32'd0;
            top1_score_pcie_q <= 32'd0;
            top1_rows_pcie_q <= 32'd0;
            top1_cycles_pcie_q <= 32'd0;
            top1_debug_status_pcie_q <= 32'd0;
            top1_debug_reader_addr_pcie_q <= 32'd0;
            top1_debug_wb_ack_count_pcie_q <= 32'd0;
            top1_debug_wb_err_count_pcie_q <= 32'd0;
            top1_debug_packet_wb_write_ack_count_pcie_q <= 32'd0;
            top1_debug_packet_wb_read_ack_count_pcie_q <= 32'd0;
            mlp_selftest_present_sync_pcie_q <= 3'd0;
            mlp_selftest_status_pcie_q <= 32'd0;
            mlp_selftest_cycle_count_pcie_q <= 32'd0;
            mlp_selftest_fail_detail_pcie_q <= 32'd0;
            mlp_selftest_fail_values_pcie_q <= 32'd0;
            mlp_selftest_first_add_sample_pcie_q <= 32'd0;
            mlp_selftest_first_requant_sample_pcie_q <= 32'd0;
            mlp_selftest_requant_debug0_pcie_q <= 32'd0;
            mlp_selftest_requant_debug1_pcie_q <= 32'd0;
            mlp_accel_status_pcie_q <= 32'd0;
            mlp_accel_cycle_count_pcie_q <= 32'd0;
            mlp_accel_output_checksum_pcie_q <= 32'd0;
            mlp_accel_output_sample0_pcie_q <= 32'd0;
            mlp_accel_output_sample1_pcie_q <= 32'd0;
            mlp_accel_output_vector_pcie_q <= 512'd0;
            m2_full_block_status_pcie_q <= 32'd0;
            m2_full_block_cycle_count_pcie_q <= 32'd0;
            m2_full_block_output_checksum_pcie_q <= 32'd0;
            m2_full_block_output_sample0_pcie_q <= 32'd0;
            m2_full_block_output_sample1_pcie_q <= 32'd0;
            m2_full_block_output_count_pcie_q <= 32'd0;
            m2_full_block_debug_pcie_q <= 32'd0;
            m2_full_block_debug1_pcie_q <= 32'd0;
            m2_full_block_debug2_pcie_q <= 32'd0;
            m2_full_block_debug3_pcie_q <= 32'd0;
            m2_full_block_provenance_pcie_q <= 32'd0;
            m2_full_block_output_hash_pcie_q <= 128'd0;
            m2_full_block_output_vector_pcie_q <= 512'd0;
            tinystories_prompt_ready_sync_pcie_q <= 3'd0;
            tinystories_busy_sync_pcie_q <= 3'd0;
            tinystories_error_sync_pcie_q <= 3'd0;
            tinystories_bridge_error_sync_pcie_q <= 3'd0;
            tinystories_error_code_pcie_q <= 8'd0;
            tinystories_debug_pcie_q <= 32'd0;
            tinystories_requests_pcie_q <= 32'd0;
            tinystories_cache_hits_pcie_q <= 32'd0;
            tinystories_cache_misses_pcie_q <= 32'd0;
            tinystories_stall_cycles_pcie_q <= 32'd0;
        end else begin
            if (pcie_command_event) begin
                payload_hold_pcie_q[0] <= pcie_command_payload[0*PAYLOAD_CHUNK_WIDTH +: PAYLOAD_CHUNK_WIDTH];
                payload_hold_pcie_q[1] <= pcie_command_payload[1*PAYLOAD_CHUNK_WIDTH +: PAYLOAD_CHUNK_WIDTH];
                payload_hold_pcie_q[2] <= pcie_command_payload[2*PAYLOAD_CHUNK_WIDTH +: PAYLOAD_CHUNK_WIDTH];
                payload_hold_pcie_q[3] <= pcie_command_payload[3*PAYLOAD_CHUNK_WIDTH +: PAYLOAD_CHUNK_WIDTH];
                req_toggle_pcie_q <= ~req_toggle_pcie_q;
            end
            if (pcie_status_clear)
                clear_toggle_pcie_q <= ~clear_toggle_pcie_q;
            if (pcie_top1_start) begin
                top1_hidden_hold_pcie_q <= pcie_top1_hidden_vector;
                top1_start_toggle_pcie_q <= ~top1_start_toggle_pcie_q;
            end
            if (pcie_top1_status_clear)
                top1_clear_toggle_pcie_q <= ~top1_clear_toggle_pcie_q;
            if (pcie_mlp_accel_start) begin
                mlp_accel_activation_hold_pcie_q <= pcie_mlp_accel_activation_vector;
                mlp_accel_residual_hold_pcie_q <= pcie_mlp_accel_residual_vector;
                mlp_accel_start_toggle_pcie_q <= ~mlp_accel_start_toggle_pcie_q;
            end
            if (pcie_mlp_accel_clear)
                mlp_accel_clear_toggle_pcie_q <= ~mlp_accel_clear_toggle_pcie_q;
            mlp_selftest_debug_select_hold_pcie_q <= pcie_mlp_selftest_debug_select;
            if (pcie_m2_full_block_start) begin
                m2_full_block_input_hold_pcie_q <= pcie_m2_full_block_input_vector;
                m2_full_block_residual_hold_pcie_q <= pcie_m2_full_block_residual_vector;
                m2_full_block_start_toggle_pcie_q <= ~m2_full_block_start_toggle_pcie_q;
            end
            if (pcie_m2_full_block_clear)
                m2_full_block_clear_toggle_pcie_q <= ~m2_full_block_clear_toggle_pcie_q;
            if (pcie_tinystories_prompt) begin
                tinystories_prompt_hold_pcie_q <= pcie_tinystories_prompt_token;
                tinystories_prompt_toggle_pcie_q <= ~tinystories_prompt_toggle_pcie_q;
            end
            if (pcie_tinystories_start) begin
                tinystories_requested_hold_pcie_q <= pcie_tinystories_requested_tokens;
                tinystories_package_tag_hold_pcie_q <= pcie_tinystories_package_tag;
                tinystories_start_toggle_pcie_q <= ~tinystories_start_toggle_pcie_q;
            end
            if (pcie_tinystories_clear)
                tinystories_clear_toggle_pcie_q <= ~tinystories_clear_toggle_pcie_q;

            calib_complete_sync_pcie_q <= {calib_complete_sync_pcie_q[1:0], rowstream_calib_complete_i};
            boot_done_sync_pcie_q <= {boot_done_sync_pcie_q[1:0], rowstream_boot_done_i};
            loader_done_sync_pcie_q <= {loader_done_sync_pcie_q[1:0], rowstream_loader_done_i};
            loader_error_sync_pcie_q <= {loader_error_sync_pcie_q[1:0], rowstream_loader_error_i};
            loader_accepted_sync_pcie_q <= {loader_accepted_sync_pcie_q[1:0], rowstream_loader_last_accepted_i};
            rowstream_rst_n_sync_pcie_q <= {rowstream_rst_n_sync_pcie_q[1:0], rowstream_rst_n};
            rowstream_heartbeat_sync_pcie_q <= {rowstream_heartbeat_sync_pcie_q[1:0], rowstream_clk_counter_q[20]};
            rowstream_heartbeat_last_pcie_q <= rowstream_heartbeat_sync_pcie_q[2];
            if (rowstream_heartbeat_edge)
                rowstream_heartbeat_count_pcie_q <= rowstream_heartbeat_count_pcie_q + 32'd1;
            rowstream_seen_pcie_q[0] <= rowstream_seen_pcie_q[0] | rowstream_heartbeat_edge;
            rowstream_seen_pcie_q[1] <= rowstream_seen_pcie_q[1] | rowstream_rst_n_sync_pcie_q[2];
            rowstream_seen_pcie_q[2] <= rowstream_seen_pcie_q[2] | calib_complete_sync_pcie_q[2];
            rowstream_seen_pcie_q[3] <= rowstream_seen_pcie_q[3] | boot_done_sync_pcie_q[2];
            rowstream_seen_pcie_q[4] <= rowstream_seen_pcie_q[4] | (rowstream_ddr_debug1_sample_pcie_q != 32'd0);
            loader_magic_ok_sync_pcie_q <= {loader_magic_ok_sync_pcie_q[1:0], rowstream_loader_last_magic_ok_i};
            loader_opcode_pcie_q <= rowstream_loader_last_opcode_i;
            loader_chunk_pcie_q <= rowstream_loader_last_chunk_i;
            loader_addr_pcie_q <= rowstream_loader_command_payload_addr_i;
            loader_wait_pcie_q <= rowstream_loader_wait_cycles_i;
            rowstream_ddr_debug1_sample_pcie_q <= rowstream_ddr_debug1_i;
            ddr_debug1_pcie_q <= rowstream_ddr_debug1_sample_pcie_q;
            loader_read_data_pcie_q <= rowstream_loader_read_data_i;
            top1_busy_sync_pcie_q <= {top1_busy_sync_pcie_q[1:0], rowstream_top1_busy_i};
            top1_done_sync_pcie_q <= {top1_done_sync_pcie_q[1:0], rowstream_top1_done_i};
            top1_error_sync_pcie_q <= {top1_error_sync_pcie_q[1:0], rowstream_top1_error_i};
            top1_token_pcie_q <= rowstream_top1_token_i;
            top1_score_pcie_q <= rowstream_top1_score_q024_i;
            top1_rows_pcie_q <= rowstream_top1_rows_scanned_i;
            top1_cycles_pcie_q <= rowstream_top1_cycle_count_i;
            top1_debug_status_pcie_q <= rowstream_top1_debug_status_i;
            top1_debug_reader_addr_pcie_q <= rowstream_top1_debug_reader_addr_i;
            top1_debug_wb_ack_count_pcie_q <= rowstream_top1_debug_wb_ack_count_i;
            top1_debug_wb_err_count_pcie_q <= rowstream_top1_debug_wb_err_count_i;
            top1_debug_packet_wb_write_ack_count_pcie_q <= rowstream_top1_debug_packet_wb_write_ack_count_i;
            top1_debug_packet_wb_read_ack_count_pcie_q <= rowstream_top1_debug_packet_wb_read_ack_count_i;
            mlp_selftest_present_sync_pcie_q <= {mlp_selftest_present_sync_pcie_q[1:0], rowstream_mlp_selftest_present_i};
            mlp_selftest_status_pcie_q <= rowstream_mlp_selftest_status_i;
            mlp_selftest_cycle_count_pcie_q <= rowstream_mlp_selftest_cycle_count_i;
            mlp_selftest_fail_detail_pcie_q <= rowstream_mlp_selftest_fail_detail_i;
            mlp_selftest_fail_values_pcie_q <= rowstream_mlp_selftest_fail_values_i;
            mlp_selftest_first_add_sample_pcie_q <= rowstream_mlp_selftest_first_add_sample_i;
            mlp_selftest_first_requant_sample_pcie_q <= rowstream_mlp_selftest_first_requant_sample_i;
            mlp_selftest_requant_debug0_pcie_q <= rowstream_mlp_selftest_requant_debug0_i;
            mlp_selftest_requant_debug1_pcie_q <= rowstream_mlp_selftest_requant_debug1_i;
            mlp_accel_status_pcie_q <= rowstream_mlp_accel_status_i;
            mlp_accel_cycle_count_pcie_q <= rowstream_mlp_accel_cycle_count_i;
            mlp_accel_output_checksum_pcie_q <= rowstream_mlp_accel_output_checksum_i;
            mlp_accel_output_sample0_pcie_q <= rowstream_mlp_accel_output_sample0_i;
            mlp_accel_output_sample1_pcie_q <= rowstream_mlp_accel_output_sample1_i;
            mlp_accel_output_vector_pcie_q <= rowstream_mlp_accel_output_vector_i;
            m2_full_block_status_pcie_q <= rowstream_m2_full_block_status_i;
            m2_full_block_cycle_count_pcie_q <= rowstream_m2_full_block_cycle_count_i;
            m2_full_block_output_checksum_pcie_q <= rowstream_m2_full_block_output_checksum_i;
            m2_full_block_output_sample0_pcie_q <= rowstream_m2_full_block_output_sample0_i;
            m2_full_block_output_sample1_pcie_q <= rowstream_m2_full_block_output_sample1_i;
            m2_full_block_output_count_pcie_q <= rowstream_m2_full_block_output_count_i;
            m2_full_block_debug_pcie_q <= rowstream_m2_full_block_debug_i;
            m2_full_block_debug1_pcie_q <= rowstream_m2_full_block_debug1_i;
            m2_full_block_debug2_pcie_q <= rowstream_m2_full_block_debug2_i;
            m2_full_block_debug3_pcie_q <= rowstream_m2_full_block_debug3_i;
            m2_full_block_provenance_pcie_q <= rowstream_m2_full_block_provenance_i;
            m2_full_block_output_hash_pcie_q <= rowstream_m2_full_block_output_hash_i;
            m2_full_block_output_vector_pcie_q <= rowstream_m2_full_block_output_vector_i;
            tinystories_prompt_ready_sync_pcie_q <= {tinystories_prompt_ready_sync_pcie_q[1:0], rowstream_tinystories_prompt_ready_i};
            tinystories_busy_sync_pcie_q <= {tinystories_busy_sync_pcie_q[1:0], rowstream_tinystories_busy_i};
            tinystories_error_sync_pcie_q <= {tinystories_error_sync_pcie_q[1:0], rowstream_tinystories_error_i};
            tinystories_bridge_error_sync_pcie_q <= {tinystories_bridge_error_sync_pcie_q[1:0], rowstream_tinystories_bridge_error_i};
            tinystories_error_code_pcie_q <= rowstream_tinystories_error_code_i;
            tinystories_debug_pcie_q <= rowstream_tinystories_debug_i;
            tinystories_requests_pcie_q <= rowstream_tinystories_requests_i;
            tinystories_cache_hits_pcie_q <= rowstream_tinystories_cache_hits_i;
            tinystories_cache_misses_pcie_q <= rowstream_tinystories_cache_misses_i;
            tinystories_stall_cycles_pcie_q <= rowstream_tinystories_stall_cycles_i;
        end
    end

    always @(posedge rowstream_clk or negedge pcie_rst_n) begin
        if (!pcie_rst_n)
            rowstream_clk_counter_q <= 32'd0;
        else
            rowstream_clk_counter_q <= rowstream_clk_counter_q + 32'd1;
    end

    always @(posedge rowstream_clk or negedge rowstream_rst_n) begin
        if (!rowstream_rst_n) begin
            req_sync_row_q <= 3'd0;
            req_seen_row_q <= 1'b0;
            clear_sync_row_q <= 3'd0;
            clear_seen_row_q <= 1'b0;
            top1_start_sync_row_q <= 3'd0;
            top1_start_seen_row_q <= 1'b0;
            top1_clear_sync_row_q <= 3'd0;
            top1_clear_seen_row_q <= 1'b0;
            mlp_accel_start_sync_row_q <= 3'd0;
            mlp_accel_start_seen_row_q <= 1'b0;
            mlp_accel_clear_sync_row_q <= 3'd0;
            mlp_accel_clear_seen_row_q <= 1'b0;
            m2_full_block_start_sync_row_q <= 3'd0;
            m2_full_block_start_seen_row_q <= 1'b0;
            m2_full_block_clear_sync_row_q <= 3'd0;
            m2_full_block_clear_seen_row_q <= 1'b0;
            tinystories_prompt_sync_row_q <= 3'd0;
            tinystories_prompt_seen_row_q <= 1'b0;
            tinystories_start_sync_row_q <= 3'd0;
            tinystories_start_seen_row_q <= 1'b0;
            tinystories_clear_sync_row_q <= 3'd0;
            tinystories_clear_seen_row_q <= 1'b0;
            rowstream_command_payload_o <= {COMMAND_WIDTH{1'b0}};
            rowstream_command_event_o <= 1'b0;
            rowstream_status_clear_o <= 1'b0;
            rowstream_top1_hidden_vector_o <= 512'd0;
            rowstream_top1_start_o <= 1'b0;
            rowstream_top1_status_clear_o <= 1'b0;
            rowstream_mlp_accel_activation_vector_o <= 512'd0;
            rowstream_mlp_accel_residual_vector_o <= 512'd0;
            rowstream_mlp_selftest_debug_select_o <= 32'd0;
            mlp_selftest_debug_select_sync1_row_q <= 32'd0;
            mlp_selftest_debug_select_sync2_row_q <= 32'd0;
            rowstream_mlp_accel_start_o <= 1'b0;
            rowstream_mlp_accel_clear_o <= 1'b0;
            rowstream_m2_full_block_input_vector_o <= 512'd0;
            rowstream_m2_full_block_residual_vector_o <= 512'd0;
            rowstream_m2_full_block_start_o <= 1'b0;
            rowstream_m2_full_block_clear_o <= 1'b0;
            rowstream_tinystories_prompt_token_o <= 16'd0;
            rowstream_tinystories_requested_tokens_o <= 8'd16;
            rowstream_tinystories_package_tag_o <= 32'd0;
            rowstream_tinystories_prompt_o <= 1'b0;
            rowstream_tinystories_start_o <= 1'b0;
            rowstream_tinystories_clear_o <= 1'b0;
        end else begin
            req_sync_row_q <= {req_sync_row_q[1:0], req_toggle_pcie_q};
            clear_sync_row_q <= {clear_sync_row_q[1:0], clear_toggle_pcie_q};
            top1_start_sync_row_q <= {top1_start_sync_row_q[1:0], top1_start_toggle_pcie_q};
            top1_clear_sync_row_q <= {top1_clear_sync_row_q[1:0], top1_clear_toggle_pcie_q};
            mlp_accel_start_sync_row_q <= {mlp_accel_start_sync_row_q[1:0], mlp_accel_start_toggle_pcie_q};
            mlp_accel_clear_sync_row_q <= {mlp_accel_clear_sync_row_q[1:0], mlp_accel_clear_toggle_pcie_q};
            m2_full_block_start_sync_row_q <= {m2_full_block_start_sync_row_q[1:0], m2_full_block_start_toggle_pcie_q};
            m2_full_block_clear_sync_row_q <= {m2_full_block_clear_sync_row_q[1:0], m2_full_block_clear_toggle_pcie_q};
            tinystories_prompt_sync_row_q <= {tinystories_prompt_sync_row_q[1:0], tinystories_prompt_toggle_pcie_q};
            tinystories_start_sync_row_q <= {tinystories_start_sync_row_q[1:0], tinystories_start_toggle_pcie_q};
            tinystories_clear_sync_row_q <= {tinystories_clear_sync_row_q[1:0], tinystories_clear_toggle_pcie_q};
            mlp_selftest_debug_select_sync1_row_q <= mlp_selftest_debug_select_hold_pcie_q;
            mlp_selftest_debug_select_sync2_row_q <= mlp_selftest_debug_select_sync1_row_q;
            rowstream_mlp_selftest_debug_select_o <= mlp_selftest_debug_select_sync2_row_q;
            rowstream_command_event_o <= 1'b0;
            rowstream_status_clear_o <= 1'b0;
            rowstream_top1_start_o <= 1'b0;
            rowstream_top1_status_clear_o <= 1'b0;
            rowstream_mlp_accel_start_o <= 1'b0;
            rowstream_mlp_accel_clear_o <= 1'b0;
            rowstream_m2_full_block_start_o <= 1'b0;
            rowstream_m2_full_block_clear_o <= 1'b0;
            rowstream_tinystories_prompt_o <= 1'b0;
            rowstream_tinystories_start_o <= 1'b0;
            rowstream_tinystories_clear_o <= 1'b0;

            if (req_sync_row_q[2] ^ req_seen_row_q) begin
                req_seen_row_q <= req_sync_row_q[2];
                rowstream_command_payload_o <= {
                    payload_hold_pcie_q[3], payload_hold_pcie_q[2],
                    payload_hold_pcie_q[1], payload_hold_pcie_q[0]
                };
                rowstream_command_event_o <= 1'b1;
            end
            if (clear_sync_row_q[2] ^ clear_seen_row_q) begin
                clear_seen_row_q <= clear_sync_row_q[2];
                rowstream_status_clear_o <= 1'b1;
            end
            if (top1_start_sync_row_q[2] ^ top1_start_seen_row_q) begin
                top1_start_seen_row_q <= top1_start_sync_row_q[2];
                rowstream_top1_hidden_vector_o <= top1_hidden_hold_pcie_q;
                rowstream_top1_start_o <= 1'b1;
            end
            if (top1_clear_sync_row_q[2] ^ top1_clear_seen_row_q) begin
                top1_clear_seen_row_q <= top1_clear_sync_row_q[2];
                rowstream_top1_status_clear_o <= 1'b1;
            end
            if (mlp_accel_start_sync_row_q[2] ^ mlp_accel_start_seen_row_q) begin
                mlp_accel_start_seen_row_q <= mlp_accel_start_sync_row_q[2];
                rowstream_mlp_accel_activation_vector_o <= mlp_accel_activation_hold_pcie_q;
                rowstream_mlp_accel_residual_vector_o <= mlp_accel_residual_hold_pcie_q;
                rowstream_mlp_accel_start_o <= 1'b1;
            end
            if (mlp_accel_clear_sync_row_q[2] ^ mlp_accel_clear_seen_row_q) begin
                mlp_accel_clear_seen_row_q <= mlp_accel_clear_sync_row_q[2];
                rowstream_mlp_accel_clear_o <= 1'b1;
            end
            if (m2_full_block_start_sync_row_q[2] ^ m2_full_block_start_seen_row_q) begin
                m2_full_block_start_seen_row_q <= m2_full_block_start_sync_row_q[2];
                rowstream_m2_full_block_input_vector_o <= m2_full_block_input_hold_pcie_q;
                rowstream_m2_full_block_residual_vector_o <= m2_full_block_residual_hold_pcie_q;
                rowstream_m2_full_block_start_o <= 1'b1;
            end
            if (m2_full_block_clear_sync_row_q[2] ^ m2_full_block_clear_seen_row_q) begin
                m2_full_block_clear_seen_row_q <= m2_full_block_clear_sync_row_q[2];
                rowstream_m2_full_block_clear_o <= 1'b1;
            end
            if (tinystories_prompt_sync_row_q[2] ^ tinystories_prompt_seen_row_q) begin
                tinystories_prompt_seen_row_q <= tinystories_prompt_sync_row_q[2];
                rowstream_tinystories_prompt_token_o <= tinystories_prompt_hold_pcie_q;
                rowstream_tinystories_prompt_o <= 1'b1;
            end
            if (tinystories_start_sync_row_q[2] ^ tinystories_start_seen_row_q) begin
                tinystories_start_seen_row_q <= tinystories_start_sync_row_q[2];
                rowstream_tinystories_requested_tokens_o <= tinystories_requested_hold_pcie_q;
                rowstream_tinystories_package_tag_o <= tinystories_package_tag_hold_pcie_q;
                rowstream_tinystories_start_o <= 1'b1;
            end
            if (tinystories_clear_sync_row_q[2] ^ tinystories_clear_seen_row_q) begin
                tinystories_clear_seen_row_q <= tinystories_clear_sync_row_q[2];
                rowstream_tinystories_clear_o <= 1'b1;
            end
        end
    end
endmodule

`default_nettype wire
