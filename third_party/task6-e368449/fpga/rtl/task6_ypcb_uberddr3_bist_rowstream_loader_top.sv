`default_nettype none

module task6_ypcb_uberddr3_bist_rowstream_loader_top #(
  parameter int JTAG_DEBUG_WIDTH = 512,
  parameter int JTAG_CHAIN = 1,
  parameter int JTAG_COMMAND_CHAIN = 2,
  parameter int PROBE_BYTE = 165,
  parameter int BYTE_LANES = 8,
  parameter int DISABLE_JTAG_DEBUG_SHIFT = (BYTE_LANES == 1),
  parameter int BOOT_ISOLATE_UNTIL_CALIB = 0,
  parameter int PLL_FB_MULT = 20,
  parameter int PLL_CLKOUT0_DIVIDE = 3,
  parameter int PLL_CLKOUT1_DIVIDE = 3,
  parameter int PLL_CLKOUT2_DIVIDE = 12,
  parameter int PLL_CLKOUT3_DIVIDE = 5,
  parameter int CONTROLLER_CLK_PERIOD_PS = 12_000,
  parameter int DDR3_CLK_PERIOD_PS = 3_000,
  parameter bit DLL_OFF_PARAM = 1'b1,
  parameter int SPEED_BIN_PARAM = 0,
  parameter int SDRAM_CAPACITY_PARAM = 5,
  parameter int BIST_MODE_PARAM = 1,
  parameter bit BIST_TEST_DATAMASK = 1'b1,
  parameter bit ENABLE_PCIE_TOP1 = 1'b1,
  parameter bit TINYSTORIES_LOADER_ONLY = 1'b0,
  parameter int TINYSTORIES_WDEPTH_BYTES = 3825235,
  parameter int TINYSTORIES_TMAX = 32,
  parameter bit TINYSTORIES_ENABLE_ENGINE = 1'b1,
  parameter bit TINYSTORIES_ENABLE_SERVICE = 1'b1,
  parameter bit TINYSTORIES_ENABLE_COMPILER_DDR3 = 1'b0,
  parameter bit TINYSTORIES_DIRECT_ACCELERATOR_OWNER = 1'b0,
  // Keep packet write/readback verification for generic loader users.  The
  // TinyStories model loader can disable this optional wide compare when
  // timing closure is required; model correctness is checked by inference.
  parameter bit TINYSTORIES_VERIFY_PACKET_WRITES = 1'b1
) (
  input  wire        clk50,
  input  wire        SYS_RSTN,
  output wire [14:0] ddram_a,
  output wire  [2:0] ddram_ba,
  output wire        ddram_cas_n,
  output wire        ddram_cke,
  output wire        ddram_clk_n,
  output wire        ddram_clk_p,
  output wire        ddram_cs_n,
  inout  wire [BYTE_LANES * 8 - 1:0] ddram_dq,
  inout  wire [BYTE_LANES - 1:0] ddram_dqs_n,
  inout  wire [BYTE_LANES - 1:0] ddram_dqs_p,
  output wire        ddram_odt,
  output wire        ddram_ras_n,
  output wire        ddram_reset_n,
  output wire        ddram_we_n
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
  , input  wire [JTAG_COMMAND_WIDTH - 1:0] pcie_command_payload_i
  , input  wire                             pcie_command_event_i
  , input  wire                             pcie_status_clear_i
  , output wire                             pcie_controller_clk_o
  , output wire                             pcie_controller_rst_n_o
  , output wire                             pcie_calib_complete_o
  , output wire                             pcie_boot_done_o
  , output wire [31:0]                      pcie_ddr_debug1_o
  , output wire                             pcie_loader_done_o
  , output wire                             pcie_loader_error_o
  , output wire                             pcie_loader_last_accepted_o
  , output wire                             pcie_loader_last_magic_ok_o
  , output wire [7:0]                       pcie_loader_last_opcode_o
  , output wire [1:0]                       pcie_loader_last_chunk_o
  , output wire [31:0]                      pcie_loader_command_payload_addr_o
  , output wire [31:0]                      pcie_loader_wait_cycles_o
  , output wire [511:0]                     pcie_loader_read_data_o
  , input  wire [511:0]                     pcie_top1_hidden_vector_i
  , input  wire                             pcie_top1_start_i
  , input  wire                             pcie_top1_status_clear_i
  , output wire                             pcie_top1_busy_o
  , output wire                             pcie_top1_done_o
  , output wire                             pcie_top1_error_o
  , output wire [31:0]                      pcie_top1_token_o
  , output wire [31:0]                      pcie_top1_score_q024_o
  , output wire [31:0]                      pcie_top1_rows_scanned_o
  , output wire [31:0]                      pcie_top1_cycle_count_o
  , output wire [31:0]                      pcie_top1_debug_status_o
  , output wire [31:0]                      pcie_top1_debug_reader_addr_o
  , output wire [31:0]                      pcie_top1_debug_wb_ack_count_o
  , output wire [31:0]                      pcie_top1_debug_wb_err_count_o
  , output wire [31:0]                      pcie_top1_debug_packet_wb_write_ack_count_o
  , output wire [31:0]                      pcie_top1_debug_packet_wb_read_ack_count_o
`endif
`ifdef TASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS
  , input  wire                             tinystories_clear_i
  , input  wire                             tinystories_prompt_valid_i
  , output wire                             tinystories_prompt_ready_o
  , input  wire [15:0]                      tinystories_prompt_token_i
  , input  wire                             tinystories_start_i
  , input  wire [5:0]                       tinystories_requested_tokens_i
  , input  wire [31:0]                      tinystories_package_tag_i
  , output wire                             tinystories_token_valid_o
  , input  wire                             tinystories_token_ready_i
  , output wire [15:0]                      tinystories_token_id_o
  , output wire                             tinystories_busy_o
  , output wire                             tinystories_error_o
  , output wire [7:0]                       tinystories_error_code_o
  , output wire [62:0]                      tinystories_debug_status_o
  , output wire                             tinystories_bridge_error_o
  , output wire [31:0]                      tinystories_request_count_o
  , output wire [31:0]                      tinystories_cache_hit_count_o
  , output wire [31:0]                      tinystories_cache_miss_count_o
  , output wire [31:0]                      tinystories_wb_read_count_o
  , output wire [31:0]                      tinystories_wb_stall_cycle_count_o
  , output wire                             tinystories_ddr_owner_active_o
  , output wire                             tinystories_ddr_accelerator_owned_o
`endif
`ifdef TASK6_COMPILER_DDR3_ACCELERATOR_PORTS
  , input wire                             compiler_wb_cyc_i
  , input wire                             compiler_wb_stb_i
  , input wire                             compiler_wb_we_i
  , input wire [24:0]                      compiler_wb_addr_i
  , input wire [8 * BYTE_LANES * 8 - 1:0] compiler_wb_data_i
  , input wire [BYTE_LANES * 8 - 1:0]     compiler_wb_sel_i
  , output wire                            compiler_wb_accept_o
  , output wire                            compiler_wb_ack_o
  , output wire                            compiler_wb_err_o
  , output wire [8 * BYTE_LANES * 8 - 1:0] compiler_wb_rdata_o
`endif
);
  localparam logic [31:0] JTAG_DEBUG_MAGIC = 32'h54364a44;
  localparam logic [7:0] JTAG_DEBUG_VERSION = 8'd63;
  localparam int JTAG_COMMAND_WIDTH = 208;
  localparam logic [31:0] LOADER_COMMAND_MAGIC = 32'h33445244;
  localparam logic [7:0] LOADER_OP_WRITE_CHUNK = 8'h01;
  localparam logic [7:0] LOADER_OP_READ_BEAT = 8'h02;
  localparam logic [7:0] LOADER_OP_WRITE_LOWBYTE = 8'h03;
  localparam logic [7:0] LOADER_OP_READ_LOWBYTE = 8'h04;
  localparam logic [7:0] LOADER_OP_WRITE_DENSE_BYTE = 8'h05;
  localparam logic [7:0] LOADER_OP_READ_DENSE_BEAT = 8'h06;
  localparam logic [7:0] LOADER_OP_RUN_AUTOPROBE = 8'h07;
  localparam logic [7:0] LOADER_OP_WRITE_DENSE_FILL = 8'h08;
  localparam logic [7:0] LOADER_OP_RUN_FULLBEAT = 8'h09;
  localparam logic [7:0] LOADER_OP_RUN_HARDCODED_AUTOPROBE = 8'h0a;
  localparam logic [7:0] LOADER_OP_RUN_HARDCODED_SINGLEBYTE = 8'h0b;
  localparam logic [7:0] LOADER_OP_ECHO_CHUNK = 8'h0c;
  localparam logic [7:0] LOADER_OP_RUN_HOST_FULLBEAT = 8'h0d;
  localparam logic [7:0] LOADER_OP_RUN_RTL_BURST = 8'h0e;
  localparam logic [7:0] LOADER_OP_LOAD_PACKET_BEAT = 8'h0f;
  localparam logic [7:0] LOADER_OP_RUN_HOST_PACKET = 8'h10;
  localparam logic [7:0] LOADER_OP_LOAD_PACKET_PAIR = 8'h11;
  localparam logic [7:0] LOADER_OP_READ_BANDWIDTH_COUNTER = 8'h12;
  localparam logic [7:0] LOADER_OP_CLEAR_BANDWIDTH_COUNTERS = 8'h13;
  localparam logic [7:0] TINYSTORIES_LOADER_ONLY_LOADER_OP_READ_DENSE_BEAT =
    LOADER_OP_READ_DENSE_BEAT;
  localparam logic [7:0] TINYSTORIES_LOADER_ONLY_LOADER_OP_LOAD_PACKET_BEAT =
    LOADER_OP_LOAD_PACKET_BEAT;
  localparam logic [7:0] TINYSTORIES_LOADER_ONLY_LOADER_OP_RUN_HOST_PACKET =
    LOADER_OP_RUN_HOST_PACKET;
  localparam logic [7:0] TINYSTORIES_LOADER_ONLY_LOADER_OP_LOAD_PACKET_PAIR =
    LOADER_OP_LOAD_PACKET_PAIR;
  localparam int ROW_BITS = 15;
  localparam int COL_BITS = 10;
  localparam int BA_BITS = 3;
  localparam int WB_ADDR_BITS = ROW_BITS + COL_BITS + BA_BITS - 3;
  localparam int WB_DATA_BITS = 8 * BYTE_LANES * 8;
  localparam int WB_SEL_BITS = WB_DATA_BITS / 8;
  localparam logic [3:0] ROW_BITS_NIBBLE = ROW_BITS % 16;
  localparam logic [3:0] COL_BITS_NIBBLE = COL_BITS % 16;
  localparam logic [3:0] BA_BITS_NIBBLE = BA_BITS % 16;
  localparam logic [3:0] BYTE_LANES_NIBBLE = BYTE_LANES % 16;
  localparam logic [3:0] WB_ADDR_BITS_NIBBLE = WB_ADDR_BITS % 16;
  localparam logic [3:0] WB_SEL_BITS_NIBBLE = WB_SEL_BITS % 16;
  localparam logic [7:0] PROBE_BYTE_VALUE = PROBE_BYTE[7:0];
  localparam logic [15:0] LOADER_HOST_FULLBEAT_COMMAND_COOLDOWN = 16'h3fff;

  function automatic logic [7:0] hardcoded_probe_value(
    input logic [1:0] selector
  );
    begin
      case (selector)
        2'd0: hardcoded_probe_value = 8'h00;
        2'd1: hardcoded_probe_value = 8'hff;
        2'd2: hardcoded_probe_value = 8'ha5;
        default: hardcoded_probe_value = 8'h5a;
      endcase
    end
  endfunction

  wire controller_clk;
  wire ddr3_clk;
  wire ddr3_clk_90;
  wire ref_clk;
  wire clk100_raw;
  wire clk100_90_raw;
  wire clk25_raw;
  wire clk200_raw;
  wire pll_clkfb;
  wire mmcm_locked;
  wire rst_n;
  logic [31:0] clk50_count_q;

  always_ff @(posedge clk50) begin
    clk50_count_q <= clk50_count_q + 32'd1;
  end

  PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),
    .CLKFBOUT_MULT(PLL_FB_MULT),
    .CLKFBOUT_PHASE(0.000),
    .CLKIN1_PERIOD(20.000),
    .CLKOUT0_DIVIDE(PLL_CLKOUT0_DIVIDE),
    .CLKOUT0_DUTY_CYCLE(0.500),
    .CLKOUT0_PHASE(0.000),
    .CLKOUT1_DIVIDE(PLL_CLKOUT1_DIVIDE),
    .CLKOUT1_DUTY_CYCLE(0.500),
    .CLKOUT1_PHASE(90.000),
    .CLKOUT2_DIVIDE(PLL_CLKOUT2_DIVIDE),
    .CLKOUT2_DUTY_CYCLE(0.500),
    .CLKOUT2_PHASE(0.000),
    .CLKOUT3_DIVIDE(PLL_CLKOUT3_DIVIDE),
    .CLKOUT3_DUTY_CYCLE(0.500),
    .CLKOUT3_PHASE(0.000),
    .DIVCLK_DIVIDE(1),
    .REF_JITTER1(0.010),
    .STARTUP_WAIT("FALSE")
  ) clock_pll (
    .CLKFBOUT(pll_clkfb),
    .CLKOUT0(clk100_raw),
    .CLKOUT1(clk100_90_raw),
    .CLKOUT2(clk25_raw),
    .CLKOUT3(clk200_raw),
    .CLKOUT4(),
    .CLKOUT5(),
    .LOCKED(mmcm_locked),
    .CLKFBIN(pll_clkfb),
    .CLKIN1(clk50),
    .PWRDWN(1'b0),
    .RST(1'b0)
  );

  BUFG clk100_bufg (
    .I(clk100_raw),
    .O(ddr3_clk)
  );

  BUFG clk100_90_bufg (
    .I(clk100_90_raw),
    .O(ddr3_clk_90)
  );

  BUFG clk25_bufg (
    .I(clk25_raw),
    .O(controller_clk)
  );

  BUFG clk200_bufg (
    .I(clk200_raw),
    .O(ref_clk)
  );

  assign rst_n = mmcm_locked;

  wire wb_stall;
  wire wb_ack;
  wire wb_err;
  wire [WB_DATA_BITS - 1:0] wb_data;
  wire memory_wb_stall;
  wire memory_wb_ack;
  wire memory_wb_err;
  wire [WB_DATA_BITS - 1:0] memory_wb_data;
  wire [3:0] wb_aux;
  wire wb2_stall;
  wire wb2_ack;
  wire [31:0] wb2_data;
  wire [0:0] ddr3_clk_p_w;
  wire [0:0] ddr3_clk_n_w;
  wire [0:0] ddr3_cke_w;
  wire [0:0] ddr3_cs_n_w;
  wire [0:0] ddr3_odt_w;
  wire [BYTE_LANES - 1:0] ddr3_dm_w;
  wire calib_complete;
  wire [31:0] debug1;
  logic ddr_ready_q;
  // Keep the wide DDR BIST debug bus out of the controller-clock ready path.
  // The extra cycle is immaterial to startup, while registering this condition
  // prevents the debug bus fanout from becoming the rowstream timing limiter.
  logic ddr_bist_done_q;
  wire uart_tx;

  typedef enum logic [3:0] {
    READ_PROBE_RESET = 3'd0,
    READ_PROBE_WAIT_CALIB = 3'd1,
    READ_PROBE_ISSUE_WRITE = 3'd2,
    READ_PROBE_WAIT_WRITE_ACK = 3'd3,
    READ_PROBE_WAIT_WRITE_DRAIN = 3'd4,
    READ_PROBE_NEXT_WRITE = 3'd5,
    READ_PROBE_ISSUE_READ = 3'd6,
    READ_PROBE_WAIT_READ_ACK = 3'd7,
    READ_PROBE_NEXT_READ = 4'd8,
    READ_PROBE_DONE = 4'd9,
    LOADER_ISSUE = 4'd10,
    LOADER_WAIT_ACK = 4'd11,
    LOADER_ERROR = 4'd12,
    LOADER_WRITE_DRAIN = 4'd13,
    LOADER_COMMAND_COOLDOWN = 4'd14,
    LOADER_BURST_NEXT = 4'd15
  } read_probe_state_t;

  typedef enum logic [1:0] {
    FULLBEAT_PHASE_NONE = 2'd0,
    FULLBEAT_PHASE_WRITE = 2'd1,
    FULLBEAT_PHASE_READ = 2'd2
  } fullbeat_phase_t;

  read_probe_state_t read_probe_state_q;
  logic read_probe_cyc_q;
  logic read_probe_stb_q;
  logic read_probe_we_q;
  logic read_probe_done_q;
  logic read_probe_write_ack_seen_q;
  logic read_probe_read_ack_seen_q;
  logic read_probe_err_seen_q;
  logic read_probe_stall_seen_q;
  logic [WB_DATA_BITS - 1:0] read_probe_data_q;
  logic [7:0] read_probe_expected_byte_q;
  logic [9:0] read_probe_write_drain_q;
  logic [31:0] read_probe_wait_cycles_q;
  logic [1:0] read_probe_write_index_q;
  logic [2:0] read_probe_read_index_q;
  logic [5:0] read_probe_stream_base_q;
  logic [31:0] read_probe_stream_bytes_q;
  logic [3:0] read_probe_stream_valid_q;
  logic [3:0] read_probe_stream_mismatch_q;
  logic [WB_ADDR_BITS - 1:0] read_probe_addr;
  logic [5:0] read_probe_write_addr;
  logic [5:0] read_probe_read_addr;
  logic [7:0] read_probe_write_byte;
  logic [1:0] read_probe_capture_index;
  logic [7:0] read_probe_capture_byte;
  logic [JTAG_COMMAND_WIDTH - 1:0] jtag_command_payload_from_shift;
  logic jtag_command_event_from_shift;
  logic [15:0] jtag_command_count;
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
  // Keep the PCIe command bundle local to the controller clock domain before
  // it fans out through the loader decoder.  The ingress has already aligned
  // payload/event, so this is a latency-only pipeline stage; it preserves the
  // command ABI while preventing the wide cross-wrapper event path from
  // becoming the rowstream critical path.
  logic [JTAG_COMMAND_WIDTH - 1:0] pcie_command_payload_q;
  logic pcie_command_event_q;
  logic [JTAG_COMMAND_WIDTH - 1:0] pcie_command_payload_qq;
  logic pcie_command_event_qq;
  always_ff @(posedge controller_clk or negedge rst_n) begin
    if (!rst_n) begin
      pcie_command_payload_q <= '0;
      pcie_command_event_q <= 1'b0;
      pcie_command_payload_qq <= '0;
      pcie_command_event_qq <= 1'b0;
    end else begin
      pcie_command_payload_q <= pcie_command_payload_i;
      pcie_command_event_q <= pcie_command_event_i;
      pcie_command_payload_qq <= pcie_command_payload_q;
      pcie_command_event_qq <= pcie_command_event_q;
    end
  end
  // The compiler-generated accelerator has a wider command/decode cone than
  // the loader-only path. Give only that mode one additional registered
  // boundary; the established loader/JTAG mode retains its one-cycle ABI.
  wire compiler_command_event = TINYSTORIES_ENABLE_COMPILER_DDR3
    ? pcie_command_event_qq : pcie_command_event_q;
  wire [JTAG_COMMAND_WIDTH - 1:0] compiler_command_payload =
    TINYSTORIES_ENABLE_COMPILER_DDR3
      ? pcie_command_payload_qq : pcie_command_payload_q;
  wire [JTAG_COMMAND_WIDTH - 1:0] jtag_command_payload =
    compiler_command_event ? compiler_command_payload : jtag_command_payload_from_shift;
  wire jtag_command_event = compiler_command_event | jtag_command_event_from_shift;
  logic pcie_loader_done_sticky_q;
  logic pcie_loader_error_sticky_q;
  logic pcie_loader_last_accepted_sticky_q;
  logic pcie_loader_last_magic_ok_sticky_q;
`else
  wire [JTAG_COMMAND_WIDTH - 1:0] jtag_command_payload = jtag_command_payload_from_shift;
  wire jtag_command_event = jtag_command_event_from_shift;
`endif
  wire [JTAG_COMMAND_WIDTH - 1:0] tinystories_staged_command_payload;
  wire tinystories_dispatch_read_dense;
  wire tinystories_dispatch_load_beat;
  wire tinystories_dispatch_run_packet;
  wire tinystories_dispatch_load_pair;
  wire tinystories_dispatch_invalid;
  wire tinystories_dispatch_any;
  wire [JTAG_COMMAND_WIDTH - 1:0] loader_command_payload =
    TINYSTORIES_LOADER_ONLY ? tinystories_staged_command_payload : jtag_command_payload;
  logic [15:0] read_probe_run_count_q;
  logic [WB_ADDR_BITS - 1:0] loader_addr_q;
  logic [WB_DATA_BITS - 1:0] loader_write_data_q;
  logic [WB_DATA_BITS - 1:0] loader_read_data_q;
  logic [WB_SEL_BITS - 1:0] loader_sel_q;
  logic loader_done_q;
  logic loader_error_q;
  logic loader_write_ack_seen_q;
  logic loader_read_ack_seen_q;
  logic loader_stall_seen_q;
  logic [31:0] loader_wait_cycles_q;
  logic [31:0] loader_command_payload_addr_q;
  logic [7:0] loader_last_opcode_q;
  logic [1:0] loader_last_chunk_q;
  logic [1:0] loader_read_chunk_q;
  logic loader_last_magic_ok_q;
  logic loader_last_accepted_q;
  logic loader_dense_write_seen_q;
  logic [15:0] loader_dense_write_addr_q;
  logic [5:0] loader_dense_write_lane_q;
  logic [7:0] loader_dense_write_data_q;
  logic [15:0] loader_dense_write_sel_low_q;
  logic [7:0] loader_lowbyte_write_data_q;
  logic [7:0] loader_lowbyte_read_data_q;
  logic [7:0] loader_lowbyte_addr_q;
  logic loader_lowbyte_read_seen_q;
  logic loader_lowbyte_write_seen_q;
  logic loader_fullbeat_read_after_write_q;
  logic loader_fullbeat_compare_active_q;
  logic loader_fullbeat_done_q;
  logic [15:0] loader_command_cooldown_q;
  logic loader_burst_active_q;
  logic loader_burst_read_phase_q;
  logic [7:0] loader_burst_count_q;
  logic [7:0] loader_burst_index_q;
  logic [7:0] loader_burst_mismatch_count_q;
  logic [7:0] loader_burst_first_mismatch_q;
  // Sticky across a complete model transfer; the per-burst fields above are
  // reset for every OP_RUN_HOST_PACKET and therefore cannot certify the image.
  logic loader_any_mismatch_q;
  logic [WB_ADDR_BITS - 1:0] loader_burst_base_addr_q;
  logic loader_burst_packet_mode_q;
  logic [WB_DATA_BITS - 1:0] loader_packet_data_q [0:3];
  logic loader_packet_write_ack_seen_q;
  logic loader_packet_read_ack_seen_q;
  logic [7:0] loader_packet_write_ack_index_q;
  logic [WB_ADDR_BITS - 1:0] loader_packet_write_ack_addr_q;
  logic [WB_DATA_BITS - 1:0] loader_packet_write_ack_data_q;
  logic [WB_SEL_BITS - 1:0] loader_packet_write_ack_sel_q;
  logic [WB_ADDR_BITS - 1:0] loader_packet_read_ack_addr_q;
  logic [WB_DATA_BITS - 1:0] loader_packet_read_ack_data_q;
  logic [6:0] loader_fullbeat_mismatch_count_q;
  logic [WB_ADDR_BITS - 1:0] loader_fullbeat_addr_q;
  logic [7:0] loader_fullbeat_expected_base_q;
  logic [31:0] loader_fullbeat_write_echo_q;
  logic [3:0] loader_debug_state;
  logic [31:0] loader_fullbeat_issue_cycle_q;
  logic [3:0] loader_fullbeat_last_write_ack_delta_q;
  logic [3:0] loader_fullbeat_last_read_ack_delta_q;
  logic [31:0] loader_standalone_read_issue_cycle_q;
  logic [3:0] loader_standalone_read_ack_delta_q;
  logic [WB_ADDR_BITS - 1:0] loader_standalone_read_request_addr_q;
  logic [WB_ADDR_BITS - 1:0] loader_standalone_read_ack_addr_q;
  logic [7:0] loader_standalone_read_ack_opcode_q;
  fullbeat_phase_t loader_fullbeat_issue_phase_q;
  logic [127:0] loader_fullbeat_last_issue_data_q;
  logic [$clog2(WB_SEL_BITS) - 1:0] loader_lowbyte_index_q;
  logic read_probe_single_q;
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
  logic top1_start_accepted;
  logic top1_start_rejected;
  logic [2:0] top1_reset_count_q;
  logic top1_reset_active;
  logic top1_done_sticky_q;
  logic top1_error_sticky_q;
  logic [31:0] top1_token_q;
  logic [31:0] top1_score_q024_q;
  logic [31:0] top1_rows_scanned_q;
  logic [31:0] top1_cycle_count_q;
  logic top1_fault_seen_q;
  logic [15:0] top1_fault_token_q;
  logic [31:0] top1_fault_sidecar_q;
  logic [WB_ADDR_BITS - 1:0] top1_fault_reader_addr_q;
  logic top1_row0_sidecar_decode_checked_q;
  logic top1_row0_sidecar_decode_mismatch_q;
  logic top1_reader_busy;
  logic top1_reader_done;
  logic top1_reader_error;
  logic top1_reader_wb_cyc;
  logic top1_reader_wb_stb;
  logic top1_reader_wb_we;
  logic [WB_ADDR_BITS - 1:0] top1_reader_wb_addr;
  logic [WB_DATA_BITS - 1:0] top1_reader_wb_data;
  logic [WB_SEL_BITS - 1:0] top1_reader_wb_sel;
  logic top1_row_valid;
  logic top1_row_ready;
  logic [15:0] top1_row_token_id;
  logic [511:0] top1_row_weight_q_i8;
  logic [31:0] top1_row_sidecar_word;
  logic top1_row_last;
  logic [63:0] top1_debug_first_row_sidecar_beat;
  logic top1_debug_first_row_sidecar_beat_valid;
  logic top1_cutout_valid;
  logic top1_cutout_done;
  logic top1_cutout_busy;
  logic top1_cutout_error_reserved_bits;
  logic [15:0] top1_cutout_token_id;
  logic signed [45:0] top1_cutout_score_q024;
  logic [31:0] top1_cutout_rows_scanned;
  logic [31:0] top1_cutout_cycle_count;
`endif
  logic read_probe_is_loader_beat;
  logic [WB_ADDR_BITS - 1:0] wb_addr_to_controller;
  logic [WB_DATA_BITS - 1:0] wb_data_to_controller;
  logic [WB_SEL_BITS - 1:0] wb_sel_to_controller;

  wire [31:0] jtag_command_magic = loader_command_payload[0 +: 32];
  wire [7:0] jtag_command_opcode = loader_command_payload[32 +: 8];
  wire [1:0] jtag_command_chunk = loader_command_payload[40 +: 2];
  wire [31:0] jtag_command_addr = loader_command_payload[48 +: 32];
  wire [7:0] jtag_command_data_byte = loader_command_payload[80 +: 8];
  wire [2:0] jtag_command_packet_count = jtag_command_addr[31:29];
  wire [WB_ADDR_BITS - 1:0] jtag_command_addr_low16 =
    {{(WB_ADDR_BITS - 16){1'b0}}, jtag_command_addr[15:0]};
  wire [WB_ADDR_BITS - 1:0] jtag_command_addr_full =
    jtag_command_addr[WB_ADDR_BITS - 1:0];
  wire jtag_command_magic_ok = jtag_command_magic == LOADER_COMMAND_MAGIC;
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
  assign top1_reset_active = top1_reset_count_q != 3'd0;
`endif
  wire [WB_ADDR_BITS - 1:0] jtag_command_lowbyte_addr =
    jtag_command_addr[WB_ADDR_BITS + $clog2(WB_SEL_BITS) - 1:$clog2(WB_SEL_BITS)];
  wire [$clog2(WB_SEL_BITS) - 1:0] jtag_command_lowbyte_index =
    jtag_command_addr[$clog2(WB_SEL_BITS) - 1:0];
  wire [WB_SEL_BITS - 1:0] jtag_command_lowbyte_sel =
    {{(WB_SEL_BITS - 1){1'b0}}, 1'b1} << jtag_command_lowbyte_index;
  wire [WB_ADDR_BITS - 1:0] jtag_command_dense_addr =
    {{(WB_ADDR_BITS - 10){1'b0}}, jtag_command_addr[15:6]};
  wire [WB_SEL_BITS - 1:0] jtag_command_dense_sel =
    {{(WB_SEL_BITS - 1){1'b0}}, 1'b1} << jtag_command_addr[5:0];
  logic [WB_DATA_BITS - 1:0] jtag_command_dense_data;
  logic [WB_DATA_BITS - 1:0] jtag_command_lowbyte_data;
  logic [WB_DATA_BITS - 1:0] jtag_command_fullbeat_data;
  logic [WB_DATA_BITS - 1:0] jtag_command_chunk_data;
  logic [127:0] jtag_command_pair_data;
  logic [WB_DATA_BITS - 1:0] loader_fullbeat_expected_data;
  logic [6:0] loader_fullbeat_mismatch_count;

  function automatic logic [WB_DATA_BITS - 1:0] generated_burst_fullbeat(
    input logic [7:0] beat_index
  );
    logic [WB_DATA_BITS - 1:0] value;
    begin
      value = '0;
      for (int lane = 0; lane < WB_SEL_BITS; lane = lane + 1)
        value[lane * 8 +: 8] = 8'h40 + beat_index + lane[7:0];
      generated_burst_fullbeat = value;
    end
  endfunction

  function automatic [3:0] clamp_delta4(
    input logic [31:0] issue_cycle,
    input logic [31:0] ack_cycle
  );
    logic [31:0] delta;
    begin
      delta = ack_cycle - issue_cycle;
      clamp_delta4 = delta > 32'd15 ? 4'hf : delta[3:0];
    end
  endfunction

  always_comb begin
    jtag_command_dense_data = '0;
    jtag_command_dense_data[jtag_command_addr[5:0] * 8 +: 8] =
      jtag_command_data_byte;
  end

  always_comb begin
    jtag_command_lowbyte_data = '0;
    jtag_command_lowbyte_data[jtag_command_lowbyte_index * 8 +: 8] =
      jtag_command_data_byte;
  end

  always_comb begin
    jtag_command_chunk_data = '0;
    jtag_command_pair_data = '0;
    for (int lane = 0; lane < WB_SEL_BITS; lane = lane + 1) begin
      if (lane < 16)
        jtag_command_chunk_data[lane * 8 +: 8] = loader_command_payload[80 + lane * 8 +: 8];
    end
    for (int lane = 0; lane < 16; lane = lane + 1)
      jtag_command_pair_data[lane * 8 +: 8] = loader_command_payload[80 + lane * 8 +: 8];
  end

  always_comb begin
    jtag_command_fullbeat_data = '0;
    for (int lane = 0; lane < WB_SEL_BITS; lane = lane + 1)
      jtag_command_fullbeat_data[lane * 8 +: 8] = jtag_command_data_byte + lane[7:0];
  end

  always_comb begin
    if (loader_burst_active_q && loader_burst_packet_mode_q) begin
      loader_fullbeat_expected_data = loader_write_data_q;
    end else if (loader_burst_active_q) begin
      loader_fullbeat_expected_data = generated_burst_fullbeat(loader_burst_index_q);
    end else begin
      loader_fullbeat_expected_data = '0;
      for (int lane = 0; lane < WB_SEL_BITS; lane = lane + 1)
        loader_fullbeat_expected_data[lane * 8 +: 8] =
          loader_fullbeat_expected_base_q + lane[7:0];
    end
  end

  always_comb begin
    loader_fullbeat_mismatch_count = 7'd0;
    for (int lane = 0; lane < WB_SEL_BITS; lane = lane + 1) begin
      if (wb_data[lane * 8 +: 8] != loader_fullbeat_expected_data[lane * 8 +: 8])
        loader_fullbeat_mismatch_count = loader_fullbeat_mismatch_count + 7'd1;
    end
  end

  assign ddram_clk_p = ddr3_clk_p_w[0];
  assign ddram_clk_n = ddr3_clk_n_w[0];
  assign ddram_cke = ddr3_cke_w[0];
  assign ddram_cs_n = ddr3_cs_n_w[0];
  assign ddram_odt = ddr3_odt_w[0];

  logic [31:0] cycle_count_q;
  logic [31:0] calib_seen_cycle_q;
  logic [31:0] wb_ack_count_q;
  logic [31:0] wb_packet_write_ack_count_q;
  logic [31:0] wb_packet_read_ack_count_q;
  logic [31:0] wb_err_count_q;
  logic [31:0] wb_stall_count_q;
  logic calib_seen_q;
  logic bandwidth_clear_q;
  wire [63:0] bandwidth_read_bytes;
  wire [63:0] bandwidth_write_bytes;
  wire [63:0] bandwidth_active_cycles;
  wire [63:0] bandwidth_stall_cycles;

  initial begin
    if (
      BYTE_LANES != 1 &&
      BYTE_LANES != 2 &&
      BYTE_LANES != 4 &&
      BYTE_LANES != 8
    ) begin
      $error("BYTE_LANES must be 1, 2, 4, or 8");
      $finish;
    end
  end
  logic jtag_command_accept_phase_q;

  assign read_probe_read_addr =
    read_probe_single_q ? read_probe_stream_base_q :
    read_probe_stream_base_q +
    {4'd0, read_probe_read_index_q == 3'd4 ? 2'd3 : read_probe_read_index_q[1:0]};
  assign read_probe_write_addr =
    read_probe_stream_base_q + {4'd0, read_probe_write_index_q};
  assign read_probe_addr =
    {{(WB_ADDR_BITS - 6) {1'b0}},
     read_probe_we_q ? read_probe_write_addr : read_probe_read_addr};
  assign read_probe_write_byte =
    read_probe_single_q ? read_probe_expected_byte_q :
    read_probe_expected_byte_q + read_probe_stream_base_q +
    {6'd0, read_probe_write_index_q};
  assign read_probe_capture_index =
    read_probe_single_q ? 2'd0 : read_probe_read_index_q[1:0] - 2'd1;
  assign read_probe_capture_byte =
    read_probe_single_q ? wb_data[7:0] :
    read_probe_capture_index == 2'd3 ? wb_data[31:24] : wb_data[7:0];
  assign read_probe_is_loader_beat =
    read_probe_state_q == LOADER_ISSUE || read_probe_state_q == LOADER_WAIT_ACK;
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
  wire wb_cyc_to_controller = top1_reader_wb_cyc || read_probe_cyc_q;
  wire wb_stb_to_controller = top1_reader_wb_cyc ? top1_reader_wb_stb : read_probe_stb_q;
  wire wb_we_to_controller = top1_reader_wb_cyc ? top1_reader_wb_we : read_probe_we_q;
  assign wb_addr_to_controller = top1_reader_wb_cyc ? top1_reader_wb_addr :
    (read_probe_is_loader_beat ? loader_addr_q : read_probe_addr);
  assign wb_data_to_controller = top1_reader_wb_cyc ? top1_reader_wb_data :
    (read_probe_is_loader_beat ? loader_write_data_q : {WB_SEL_BITS{read_probe_write_byte}});
  assign wb_sel_to_controller = top1_reader_wb_cyc ? top1_reader_wb_sel :
    (read_probe_is_loader_beat ? loader_sel_q : {WB_SEL_BITS{1'b1}});
`else
  wire wb_cyc_to_controller = read_probe_cyc_q;
  wire wb_stb_to_controller = read_probe_stb_q;
  wire wb_we_to_controller = read_probe_we_q;
  assign wb_addr_to_controller =
    read_probe_is_loader_beat ? loader_addr_q : read_probe_addr;
  assign wb_data_to_controller =
    read_probe_is_loader_beat ? loader_write_data_q : {WB_SEL_BITS{read_probe_write_byte}};
  assign wb_sel_to_controller =
    read_probe_is_loader_beat ? loader_sel_q : {WB_SEL_BITS{1'b1}};
`endif
  wire memory_wb_cyc_to_controller;
  wire memory_wb_stb_to_controller;
  wire memory_wb_we_to_controller;
  wire [WB_ADDR_BITS - 1:0] memory_wb_addr_to_controller;
  wire [WB_DATA_BITS - 1:0] memory_wb_data_to_controller;
  wire [WB_SEL_BITS - 1:0] memory_wb_sel_to_controller;

`ifdef TASK6_TINYSTORIES_DDR_ACCELERATOR_PORTS
`ifdef TASK6_COMPILER_DDR3_ACCELERATOR_PORTS
  // Compiler-only image: select the generated accelerator and physical DDR3
  // port at preprocessing time.  Do not elaborate or even parse the legacy
  // reference-service RTL in this build.
  generate if (TINYSTORIES_ENABLE_COMPILER_DDR3) begin : gen_tinystories_compiler_ddr3
    wire compiler_wb_stall;
    // Preserve loader writes/readback before inference. Hold ownership for
    // each Wishbone cycle so an accelerator request cannot steal a pending
    // loader response (or vice versa).
    task6_wishbone_owner_mux #(
      .ADDR_BITS(WB_ADDR_BITS), .DATA_BITS(WB_DATA_BITS),
      .DIRECT_ACCELERATOR_OWNER(1'b0)
    ) compiler_loader_owner_mux (
      .clk(controller_clk), .rst(!rst_n), .accelerator_enable(1'b1),
      .host_cyc(wb_cyc_to_controller), .host_stb(wb_stb_to_controller),
      .host_we(wb_we_to_controller), .host_addr(wb_addr_to_controller),
      .host_write_data(wb_data_to_controller), .host_sel(wb_sel_to_controller),
      .host_stall(wb_stall), .host_ack(wb_ack), .host_err(wb_err),
      .host_read_data(wb_data),
      .accelerator_cyc(compiler_wb_cyc_i), .accelerator_stb(compiler_wb_stb_i),
      .accelerator_we(compiler_wb_we_i), .accelerator_addr(compiler_wb_addr_i),
      .accelerator_write_data(compiler_wb_data_i), .accelerator_sel(compiler_wb_sel_i),
      .accelerator_stall(compiler_wb_stall), .accelerator_ack(compiler_wb_ack_o),
      .accelerator_err(compiler_wb_err_o), .accelerator_read_data(compiler_wb_rdata_o),
      .memory_cyc(memory_wb_cyc_to_controller), .memory_stb(memory_wb_stb_to_controller),
      .memory_we(memory_wb_we_to_controller), .memory_addr(memory_wb_addr_to_controller),
      .memory_write_data(memory_wb_data_to_controller), .memory_sel(memory_wb_sel_to_controller),
      .memory_stall(memory_wb_stall), .memory_ack(memory_wb_ack),
      .memory_err(memory_wb_err), .memory_read_data(memory_wb_data),
      .owner_active(), .accelerator_owned()
    );
    assign compiler_wb_accept_o = !compiler_wb_stall;
  end else begin : gen_compiler_ddr3_disabled
    assign memory_wb_cyc_to_controller = wb_cyc_to_controller;
    assign memory_wb_stb_to_controller = wb_stb_to_controller;
    assign memory_wb_we_to_controller = wb_we_to_controller;
    assign memory_wb_addr_to_controller = wb_addr_to_controller;
    assign memory_wb_data_to_controller = wb_data_to_controller;
    assign memory_wb_sel_to_controller = wb_sel_to_controller;
    assign wb_stall = memory_wb_stall;
    assign wb_ack = memory_wb_ack;
    assign wb_err = memory_wb_err;
    assign wb_data = memory_wb_data;
    assign compiler_wb_accept_o = 1'b0;
    assign compiler_wb_ack_o = 1'b0;
    assign compiler_wb_err_o = 1'b0;
    assign compiler_wb_rdata_o = '0;
  end endgenerate
  assign tinystories_prompt_ready_o = 1'b0;
  assign tinystories_token_valid_o = 1'b0;
  assign tinystories_token_id_o = 16'd0;
  assign tinystories_busy_o = 1'b0;
  assign tinystories_error_o = 1'b0;
  assign tinystories_error_code_o = 8'd0;
  assign tinystories_debug_status_o = 63'd0;
  assign tinystories_bridge_error_o = 1'b0;
  assign tinystories_request_count_o = 32'd0;
  assign tinystories_cache_hit_count_o = 32'd0;
  assign tinystories_cache_miss_count_o = 32'd0;
  assign tinystories_wb_read_count_o = 32'd0;
  assign tinystories_wb_stall_cycle_count_o = 32'd0;
  assign tinystories_ddr_owner_active_o = compiler_wb_cyc_i;
  assign tinystories_ddr_accelerator_owned_o = compiler_wb_cyc_i;
`else
`ifdef TASK6_TINYSTORIES_JTAG_BRIDGE
  wire tinystories_bridge_clear;
  wire tinystories_bridge_prompt_valid;
  wire [15:0] tinystories_bridge_prompt_token;
  wire tinystories_bridge_start;
  wire [5:0] tinystories_bridge_requested_tokens;
  wire [31:0] tinystories_bridge_package_tag;
  wire tinystories_bridge_token_ready;
  wire [511:0] tinystories_bridge_result_payload;
  wire tinystories_service_clear = tinystories_bridge_clear;
  wire tinystories_service_prompt_valid = tinystories_bridge_prompt_valid;
  wire [15:0] tinystories_service_prompt_token = tinystories_bridge_prompt_token;
  wire tinystories_service_start = tinystories_bridge_start;
  wire [5:0] tinystories_service_requested_tokens = tinystories_bridge_requested_tokens;
  wire [31:0] tinystories_service_package_tag = tinystories_bridge_package_tag;
  wire tinystories_service_token_ready = tinystories_bridge_token_ready;
`else
  wire tinystories_service_clear = tinystories_clear_i;
  wire tinystories_service_prompt_valid = tinystories_prompt_valid_i;
  wire [15:0] tinystories_service_prompt_token = tinystories_prompt_token_i;
  wire tinystories_service_start = tinystories_start_i;
  wire [5:0] tinystories_service_requested_tokens = tinystories_requested_tokens_i;
  wire [31:0] tinystories_service_package_tag = tinystories_package_tag_i;
  wire tinystories_service_token_ready = tinystories_token_ready_i;
`endif
  generate if (TINYSTORIES_ENABLE_SERVICE) begin : gen_tinystories_service
  wire service_wb_cyc;
  wire service_wb_stb;
  wire service_wb_we;
  wire [WB_ADDR_BITS - 1:0] service_wb_addr;
  wire [WB_DATA_BITS - 1:0] service_wb_write_data;
  wire [WB_SEL_BITS - 1:0] service_wb_sel;
  wire service_wb_stall;
  wire service_wb_ack;
  wire service_wb_err;
  wire [WB_DATA_BITS - 1:0] service_wb_read_data;

  task6_tinystories_ddr_service #(
    .WDEPTH_BYTES(TINYSTORIES_WDEPTH_BYTES),
    .WB_ADDR_BITS(WB_ADDR_BITS),
    .WB_DATA_BITS(WB_DATA_BITS),
    .TMAX(TINYSTORIES_TMAX),
    .ENABLE_ENGINE(TINYSTORIES_ENABLE_ENGINE),
    .DIRECT_ACCELERATOR_OWNER(TINYSTORIES_DIRECT_ACCELERATOR_OWNER)
  ) tinystories_ddr_service (
    .clk(controller_clk),.rst(!rst_n),.clear(tinystories_service_clear),
    .prompt_valid(tinystories_service_prompt_valid),
    .prompt_ready(tinystories_prompt_ready_o),
    .prompt_token(tinystories_service_prompt_token),.start(tinystories_service_start),
    .requested_tokens(tinystories_service_requested_tokens),
    .package_tag(tinystories_service_package_tag),
    .token_valid(tinystories_token_valid_o),
    .token_ready(tinystories_service_token_ready),.token_id(tinystories_token_id_o),
    .busy(tinystories_busy_o),.error(tinystories_error_o),
    .error_code(tinystories_error_code_o),
    .debug_status(tinystories_debug_status_o),
    .host_wb_cyc(wb_cyc_to_controller),.host_wb_stb(wb_stb_to_controller),
    .host_wb_we(wb_we_to_controller),.host_wb_addr(wb_addr_to_controller),
    .host_wb_write_data(wb_data_to_controller),.host_wb_sel(wb_sel_to_controller),
    .host_wb_stall(wb_stall),.host_wb_ack(wb_ack),.host_wb_err(wb_err),
    .host_wb_read_data(wb_data),
    .memory_wb_cyc(service_wb_cyc),
    .memory_wb_stb(service_wb_stb),
    .memory_wb_we(service_wb_we),
    .memory_wb_addr(service_wb_addr),
    .memory_wb_write_data(service_wb_write_data),
    .memory_wb_sel(service_wb_sel),
    .memory_wb_stall(service_wb_stall),.memory_wb_ack(service_wb_ack),
    .memory_wb_err(service_wb_err),.memory_wb_read_data(service_wb_read_data),
    .bridge_error(tinystories_bridge_error_o),
    .request_count(tinystories_request_count_o),
    .cache_hit_count(tinystories_cache_hit_count_o),
    .cache_miss_count(tinystories_cache_miss_count_o),
    .wb_read_count(tinystories_wb_read_count_o),
    .wb_stall_cycle_count(tinystories_wb_stall_cycle_count_o),
    .owner_active(tinystories_ddr_owner_active_o),
    .accelerator_owned(tinystories_ddr_accelerator_owned_o)
  );

  // Keep the accelerator Wishbone path direct.  The DDR controller already
  // provides a registered response; an extra request register can lose the
  // narrow hardware ACK/data phase.
  assign memory_wb_cyc_to_controller = service_wb_cyc;
  assign memory_wb_stb_to_controller = service_wb_stb;
  assign memory_wb_we_to_controller = service_wb_we;
  assign memory_wb_addr_to_controller = service_wb_addr;
  assign memory_wb_data_to_controller = service_wb_write_data;
  assign memory_wb_sel_to_controller = service_wb_sel;
  assign service_wb_stall = memory_wb_stall;
  assign service_wb_ack = memory_wb_ack;
  assign service_wb_err = memory_wb_err;
  assign service_wb_read_data = memory_wb_data;
  end else begin : gen_tinystories_service_bypass
    assign tinystories_prompt_ready_o = 1'b0;
    assign tinystories_token_valid_o = 1'b0;
    assign tinystories_token_id_o = 16'd0;
    assign tinystories_busy_o = 1'b0;
    assign tinystories_error_o = 1'b0;
    assign tinystories_error_code_o = 8'd0;
    assign tinystories_debug_status_o = 63'd0;
    assign tinystories_bridge_error_o = 1'b0;
    assign tinystories_request_count_o = 32'd0;
    assign tinystories_cache_hit_count_o = 32'd0;
    assign tinystories_cache_miss_count_o = 32'd0;
    assign tinystories_wb_read_count_o = 32'd0;
    assign tinystories_wb_stall_cycle_count_o = 32'd0;
    assign tinystories_ddr_owner_active_o = 1'b0;
    assign tinystories_ddr_accelerator_owned_o = 1'b0;
    assign memory_wb_cyc_to_controller = wb_cyc_to_controller;
    assign memory_wb_stb_to_controller = wb_stb_to_controller;
    assign memory_wb_we_to_controller = wb_we_to_controller;
    assign memory_wb_addr_to_controller = wb_addr_to_controller;
    assign memory_wb_data_to_controller = wb_data_to_controller;
    assign memory_wb_sel_to_controller = wb_sel_to_controller;
    assign wb_stall = memory_wb_stall;
    assign wb_ack = memory_wb_ack;
    assign wb_err = memory_wb_err;
    assign wb_data = memory_wb_data;
  end endgenerate
`ifdef TASK6_TINYSTORIES_JTAG_BRIDGE
  task6_tinystories_jtag_bridge tinystories_jtag_bridge (
    .clk(controller_clk), .rst(!rst_n),
    .command_payload(jtag_command_payload),
    .command_event(jtag_command_event),
    .clear(tinystories_bridge_clear),
    .prompt_valid(tinystories_bridge_prompt_valid),
    .prompt_token(tinystories_bridge_prompt_token),
    .start(tinystories_bridge_start),
    .requested_tokens(tinystories_bridge_requested_tokens),
    .package_tag(tinystories_bridge_package_tag),
    .prompt_ready(tinystories_prompt_ready_o),
    .token_valid(tinystories_token_valid_o),
    .token_ready(tinystories_bridge_token_ready),
    .token_id(tinystories_token_id_o),
    .busy(tinystories_busy_o), .error(tinystories_error_o),
    .error_code(tinystories_error_code_o),
    .debug_status(tinystories_debug_status_o),
    .bridge_error(tinystories_bridge_error_o),
    .request_count(tinystories_request_count_o),
    .cache_hit_count(tinystories_cache_hit_count_o),
    .cache_miss_count(tinystories_cache_miss_count_o),
    .stall_cycles(tinystories_wb_stall_cycle_count_o),
    .result_payload(tinystories_bridge_result_payload)
  );
`endif
`endif
`else
  assign memory_wb_cyc_to_controller = wb_cyc_to_controller;
  assign memory_wb_stb_to_controller = wb_stb_to_controller;
  assign memory_wb_we_to_controller = wb_we_to_controller;
  assign memory_wb_addr_to_controller = wb_addr_to_controller;
  assign memory_wb_data_to_controller = wb_data_to_controller;
  assign memory_wb_sel_to_controller = wb_sel_to_controller;
  assign wb_stall = memory_wb_stall;
  assign wb_ack = memory_wb_ack;
  assign wb_err = memory_wb_err;
  assign wb_data = memory_wb_data;
`endif
  wire tinystories_command_capture_enable =
    TINYSTORIES_LOADER_ONLY && !jtag_command_accept_phase_q &&
    read_probe_done_q && ddr_ready_q
`ifdef TASK6_TINYSTORIES_JTAG_BRIDGE
    && jtag_command_payload[0 +: 32] == LOADER_COMMAND_MAGIC
`endif
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
    && !top1_reader_busy
`endif
    ;

  task6_tinystories_loader_command_stage tinystories_loader_command_stage (
    .clk(controller_clk),.rst(!rst_n),
    .capture_enable(tinystories_command_capture_enable),
    .command_event(jtag_command_event),.command_payload(jtag_command_payload),
    .staged_payload(tinystories_staged_command_payload),
    .dispatch_read_dense(tinystories_dispatch_read_dense),
    .dispatch_load_beat(tinystories_dispatch_load_beat),
    .dispatch_run_packet(tinystories_dispatch_run_packet),
    .dispatch_load_pair(tinystories_dispatch_load_pair),
    .dispatch_invalid(tinystories_dispatch_invalid),
    .dispatch_any(tinystories_dispatch_any)
  );

  assign loader_debug_state =
    read_probe_state_q == LOADER_ISSUE ? 4'd2 :
    read_probe_state_q == LOADER_WAIT_ACK ? 4'd3 :
    read_probe_state_q == LOADER_ERROR ? 4'd4 :
    read_probe_state_q == LOADER_WRITE_DRAIN ? 4'd5 :
    read_probe_done_q ? 4'd1 :
    read_probe_state_q;

  always_ff @(posedge controller_clk or negedge rst_n) begin
    if (!rst_n) begin
      cycle_count_q <= 32'd0;
      calib_seen_cycle_q <= 32'd0;
      wb_ack_count_q <= 32'd0;
      wb_packet_write_ack_count_q <= 32'd0;
      wb_packet_read_ack_count_q <= 32'd0;
      wb_err_count_q <= 32'd0;
      wb_stall_count_q <= 32'd0;
      calib_seen_q <= 1'b0;
      ddr_ready_q <= 1'b0;
      ddr_bist_done_q <= 1'b0;
      bandwidth_clear_q <= 1'b0;
      jtag_command_accept_phase_q <= 1'b0;
      read_probe_state_q <= READ_PROBE_RESET;
      read_probe_cyc_q <= 1'b0;
      read_probe_stb_q <= 1'b0;
      read_probe_we_q <= 1'b0;
      read_probe_done_q <= 1'b0;
      read_probe_write_ack_seen_q <= 1'b0;
      read_probe_read_ack_seen_q <= 1'b0;
      read_probe_err_seen_q <= 1'b0;
      read_probe_stall_seen_q <= 1'b0;
      read_probe_data_q <= '0;
      read_probe_expected_byte_q <= PROBE_BYTE_VALUE;
      read_probe_write_drain_q <= 10'd0;
      read_probe_wait_cycles_q <= 32'd0;
      read_probe_write_index_q <= 2'd0;
      read_probe_read_index_q <= 3'd0;
      read_probe_stream_base_q <= 6'd0;
      read_probe_stream_bytes_q <= '0;
      read_probe_stream_valid_q <= 4'd0;
      read_probe_stream_mismatch_q <= 4'd0;
      read_probe_run_count_q <= 16'd0;
      loader_addr_q <= '0;
      loader_write_data_q <= '0;
      loader_read_data_q <= '0;
      loader_sel_q <= '0;
      loader_lowbyte_index_q <= '0;
      loader_done_q <= 1'b0;
      loader_error_q <= 1'b0;
      loader_write_ack_seen_q <= 1'b0;
      loader_read_ack_seen_q <= 1'b0;
      loader_stall_seen_q <= 1'b0;
      loader_wait_cycles_q <= 32'd0;
      loader_command_payload_addr_q <= 32'd0;
      loader_last_opcode_q <= 8'd0;
      loader_last_chunk_q <= 2'd0;
      loader_read_chunk_q <= 2'd0;
      loader_last_magic_ok_q <= 1'b0;
      loader_last_accepted_q <= 1'b0;

      loader_any_mismatch_q <= 1'b0;
      loader_dense_write_seen_q <= 1'b0;
      loader_dense_write_addr_q <= 16'd0;
      loader_dense_write_lane_q <= 6'd0;
      loader_dense_write_data_q <= 8'd0;
      loader_dense_write_sel_low_q <= 16'd0;
      loader_lowbyte_write_data_q <= 8'd0;
      loader_lowbyte_read_data_q <= 8'd0;
      loader_lowbyte_addr_q <= 8'd0;
      loader_lowbyte_read_seen_q <= 1'b0;
      loader_lowbyte_write_seen_q <= 1'b0;
      loader_fullbeat_read_after_write_q <= 1'b0;
      loader_fullbeat_compare_active_q <= 1'b0;
      loader_fullbeat_done_q <= 1'b0;
      loader_command_cooldown_q <= 16'd0;
      loader_burst_active_q <= 1'b0;
      loader_burst_read_phase_q <= 1'b0;
      loader_burst_count_q <= 8'd0;
      loader_burst_index_q <= 8'd0;
      loader_burst_mismatch_count_q <= 8'd0;
      loader_burst_first_mismatch_q <= 8'hff;
      loader_burst_base_addr_q <= '0;
      loader_burst_packet_mode_q <= 1'b0;
      for (int packet_reset_index = 0; packet_reset_index < 4; packet_reset_index = packet_reset_index + 1)
        loader_packet_data_q[packet_reset_index] <= '0;
      loader_packet_write_ack_seen_q <= 1'b0;
      loader_packet_read_ack_seen_q <= 1'b0;
      loader_packet_write_ack_index_q <= 8'd0;
      loader_packet_write_ack_addr_q <= '0;
      loader_packet_write_ack_data_q <= '0;
      loader_packet_write_ack_sel_q <= '0;
      loader_packet_read_ack_addr_q <= '0;
      loader_packet_read_ack_data_q <= '0;
      loader_fullbeat_mismatch_count_q <= 7'd0;
      loader_fullbeat_addr_q <= '0;
      loader_fullbeat_expected_base_q <= 8'd0;
      loader_fullbeat_write_echo_q <= 32'd0;
      loader_fullbeat_issue_cycle_q <= 32'd0;
      loader_fullbeat_last_write_ack_delta_q <= 4'd0;
      loader_fullbeat_last_read_ack_delta_q <= 4'd0;
      loader_standalone_read_issue_cycle_q <= 32'd0;
      loader_standalone_read_ack_delta_q <= 4'd0;
      loader_standalone_read_request_addr_q <= '0;
      loader_standalone_read_ack_addr_q <= '0;
      loader_standalone_read_ack_opcode_q <= 8'd0;
      loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
      loader_fullbeat_last_issue_data_q <= '0;
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
      top1_reset_count_q <= 3'd0;
      top1_done_sticky_q <= 1'b0;
      top1_error_sticky_q <= 1'b0;
      top1_token_q <= 32'd0;
      top1_score_q024_q <= 32'd0;
      top1_rows_scanned_q <= 32'd0;
      top1_cycle_count_q <= 32'd0;
      top1_fault_seen_q <= 1'b0;
      top1_fault_token_q <= 16'd0;
      top1_fault_sidecar_q <= 32'd0;
      top1_fault_reader_addr_q <= '0;
      top1_row0_sidecar_decode_checked_q <= 1'b0;
      top1_row0_sidecar_decode_mismatch_q <= 1'b0;
`endif
      read_probe_single_q <= 1'b0;
    end else begin
      bandwidth_clear_q <= 1'b0;
      // calib_complete is the DDR controller's supported readiness boundary.
      // Do not feed the wide BIST debug bus into this clock domain's control
      // cone; that fanout was the routed rowstream timing limiter.
      ddr_bist_done_q <= calib_complete;
      ddr_ready_q <= ddr_bist_done_q;
      // A packet-loader image starts with slot zero at address zero.  Clear
      // the sticky aggregate only at that boundary (the command is duplicated
      // by the JTAG CDC protocol, so clearing twice is harmless).
      if (tinystories_dispatch_load_beat && jtag_command_addr == 32'd0)
        loader_any_mismatch_q <= 1'b0;
      cycle_count_q <= cycle_count_q + 32'd1;
      if (calib_complete && !calib_seen_q) begin
        calib_seen_q <= 1'b1;
        calib_seen_cycle_q <= cycle_count_q;
      end
      if (wb_ack)
        wb_ack_count_q <= wb_ack_count_q + 32'd1;
      if (wb_err)
        wb_err_count_q <= wb_err_count_q + 32'd1;
      if (wb_stall)
        wb_stall_count_q <= wb_stall_count_q + 32'd1;

      if (jtag_command_event)
        jtag_command_accept_phase_q <= ~jtag_command_accept_phase_q;

`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
      if (pcie_status_clear_i) begin
        pcie_loader_done_sticky_q <= 1'b0;
        pcie_loader_error_sticky_q <= 1'b0;
        pcie_loader_last_accepted_sticky_q <= 1'b0;
        pcie_loader_last_magic_ok_sticky_q <= 1'b0;
      end else begin
        if (loader_done_q)
          pcie_loader_done_sticky_q <= 1'b1;
        if (loader_error_q)
          pcie_loader_error_sticky_q <= 1'b1;
        if (loader_last_accepted_q)
          pcie_loader_last_accepted_sticky_q <= 1'b1;
        if (loader_last_magic_ok_q)
          pcie_loader_last_magic_ok_sticky_q <= 1'b1;
      end

      if (top1_reset_count_q != 3'd0)
        top1_reset_count_q <= top1_reset_count_q - 3'd1;
      if (pcie_top1_status_clear_i) begin
        top1_reset_count_q <= 3'd4;
        top1_done_sticky_q <= 1'b0;
        top1_error_sticky_q <= 1'b0;
        top1_token_q <= 32'd0;
        top1_score_q024_q <= 32'd0;
        top1_rows_scanned_q <= 32'd0;
        top1_cycle_count_q <= 32'd0;
        top1_fault_seen_q <= 1'b0;
        top1_fault_token_q <= 16'd0;
        top1_fault_sidecar_q <= 32'd0;
        top1_fault_reader_addr_q <= '0;
        top1_row0_sidecar_decode_checked_q <= 1'b0;
        top1_row0_sidecar_decode_mismatch_q <= 1'b0;
      end
      if (top1_start_accepted) begin
        top1_done_sticky_q <= 1'b0;
        top1_error_sticky_q <= 1'b0;
        top1_fault_seen_q <= 1'b0;
        top1_fault_token_q <= 16'd0;
        top1_fault_sidecar_q <= 32'd0;
        top1_fault_reader_addr_q <= '0;
        top1_row0_sidecar_decode_checked_q <= 1'b0;
        top1_row0_sidecar_decode_mismatch_q <= 1'b0;
      end else if (top1_start_rejected && !pcie_top1_status_clear_i) begin
        top1_error_sticky_q <= 1'b1;
      end
      if (
        top1_row_valid && top1_row_ready && top1_row_token_id == 16'd0 &&
        top1_debug_first_row_sidecar_beat_valid &&
        !top1_row0_sidecar_decode_checked_q && !pcie_top1_status_clear_i
      ) begin
        top1_row0_sidecar_decode_checked_q <= 1'b1;
        top1_row0_sidecar_decode_mismatch_q <=
          top1_row_sidecar_word != top1_debug_first_row_sidecar_beat[31:0];
      end
      if (
        top1_row_valid && top1_row_ready && |top1_row_sidecar_word[31:24] &&
        !top1_fault_seen_q && !pcie_top1_status_clear_i
      ) begin
        top1_fault_seen_q <= 1'b1;
        top1_fault_token_q <= top1_row_token_id;
        top1_fault_sidecar_q <= top1_row_sidecar_word;
        top1_fault_reader_addr_q <= top1_reader_wb_addr;
      end
      if ((top1_reader_error || top1_cutout_error_reserved_bits) && !pcie_top1_status_clear_i)
        top1_error_sticky_q <= 1'b1;
      if (top1_cutout_done && !top1_done_sticky_q && !pcie_top1_status_clear_i) begin
        top1_done_sticky_q <= 1'b1;
        top1_token_q <= {16'd0, top1_cutout_token_id};
        top1_score_q024_q <= top1_cutout_score_q024[31:0];
        top1_rows_scanned_q <= top1_cutout_rows_scanned;
        top1_cycle_count_q <= top1_cutout_cycle_count;
      end
`endif
      loader_done_q <= 1'b0;
      loader_last_accepted_q <= 1'b0;

      if (
        tinystories_dispatch_any ||
        (!TINYSTORIES_LOADER_ONLY && jtag_command_event &&
         !jtag_command_accept_phase_q && read_probe_done_q &&
         jtag_command_magic_ok && ddr_ready_q
`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
         && !top1_reader_busy
`endif
        )
      ) begin
        loader_last_opcode_q <= jtag_command_opcode;
        loader_last_chunk_q <= jtag_command_chunk;
        loader_command_payload_addr_q <= jtag_command_addr;
        loader_last_magic_ok_q <= 1'b1;
        loader_last_accepted_q <= 1'b1;
        read_probe_done_q <= 1'b0;
        loader_error_q <= 1'b0;
        loader_stall_seen_q <= 1'b0;
        loader_wait_cycles_q <= 32'd0;
        loader_fullbeat_read_after_write_q <= 1'b0;
        loader_fullbeat_compare_active_q <= 1'b0;
        loader_burst_active_q <= 1'b0;
        loader_burst_read_phase_q <= 1'b0;
        loader_burst_packet_mode_q <= 1'b0;
        loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
        if (TINYSTORIES_LOADER_ONLY) begin
          if (tinystories_dispatch_read_dense) begin
            loader_addr_q <= jtag_command_addr[WB_ADDR_BITS - 1:0];
            loader_read_chunk_q <= 2'd0;
            loader_sel_q <= {WB_SEL_BITS{1'b1}};
            read_probe_cyc_q <= 1'b1;
            read_probe_stb_q <= 1'b1;
            read_probe_we_q <= 1'b0;
            read_probe_state_q <= LOADER_ISSUE;
          end else if (tinystories_dispatch_load_beat && WB_SEL_BITS <= 16) begin
            loader_packet_data_q[jtag_command_addr[1:0]] <= jtag_command_chunk_data;
            loader_read_data_q <= jtag_command_chunk_data;
            loader_done_q <= 1'b1;
            read_probe_done_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_stb_q <= 1'b0;
            read_probe_we_q <= 1'b0;
            read_probe_state_q <= READ_PROBE_DONE;
          end else if (tinystories_dispatch_load_pair && WB_SEL_BITS == 8) begin
            loader_packet_data_q[jtag_command_addr[1:0]] <= jtag_command_pair_data[0 +: 64];
            if (jtag_command_addr[1:0] != 2'h3)
              loader_packet_data_q[jtag_command_addr[1:0] + 2'd1] <= jtag_command_pair_data[64 +: 64];
            loader_read_data_q <= '0;
            loader_read_data_q[0 +: 64] <= jtag_command_pair_data[0 +: 64];
            read_probe_data_q[0 +: 128] <= jtag_command_pair_data;
            loader_done_q <= 1'b1;
            read_probe_done_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_stb_q <= 1'b0;
            read_probe_we_q <= 1'b0;
            read_probe_state_q <= READ_PROBE_DONE;
          end else if (tinystories_dispatch_run_packet && WB_SEL_BITS <= 16) begin
            loader_addr_q <= jtag_command_addr_full;
            loader_write_data_q <= loader_packet_data_q[0];
            loader_sel_q <= {WB_SEL_BITS{1'b1}};
            loader_fullbeat_read_after_write_q <= TINYSTORIES_VERIFY_PACKET_WRITES;
            loader_fullbeat_compare_active_q <= 1'b0;
            loader_fullbeat_done_q <= 1'b0;
            loader_fullbeat_mismatch_count_q <= 7'd0;
            loader_fullbeat_addr_q <= jtag_command_addr_full;
            loader_burst_base_addr_q <= jtag_command_addr_full;
            loader_fullbeat_expected_base_q <= 8'h00;
            loader_fullbeat_write_echo_q <= loader_packet_data_q[0][0 +: 32];
            loader_fullbeat_issue_cycle_q <= 32'd0;
            loader_fullbeat_last_write_ack_delta_q <= 4'd0;
            loader_fullbeat_last_read_ack_delta_q <= 4'd0;
            loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
            loader_fullbeat_last_issue_data_q <= '0;
            loader_burst_active_q <= 1'b1;
            loader_burst_packet_mode_q <= 1'b1;
            loader_burst_read_phase_q <= 1'b0;
            loader_burst_count_q <= jtag_command_packet_count == 3'd0 ? 8'd0 :
              (jtag_command_packet_count > 3'd4 ? 8'd3 : {5'd0, jtag_command_packet_count} - 8'd1);
            loader_burst_index_q <= 8'd0;
            loader_burst_mismatch_count_q <= 8'd0;
            loader_burst_first_mismatch_q <= 8'hff;
            loader_packet_write_ack_seen_q <= 1'b0;
            loader_packet_read_ack_seen_q <= 1'b0;
            loader_packet_write_ack_index_q <= 8'd0;
            loader_packet_write_ack_addr_q <= '0;
            loader_packet_write_ack_data_q <= '0;
            loader_packet_write_ack_sel_q <= '0;
            loader_packet_read_ack_addr_q <= '0;
            loader_packet_read_ack_data_q <= '0;
            read_probe_cyc_q <= 1'b1;
            read_probe_stb_q <= 1'b1;
            read_probe_we_q <= 1'b1;
            read_probe_state_q <= LOADER_ISSUE;
          end else begin
            loader_error_q <= 1'b1;
            read_probe_state_q <= LOADER_ERROR;
          end
        end else if (jtag_command_opcode == LOADER_OP_READ_BANDWIDTH_COUNTER && jtag_command_chunk == 2'd0) begin
          loader_read_data_q <= '0;
          case (jtag_command_addr[1:0])
            2'd0: loader_read_data_q[0 +: 64] <= bandwidth_read_bytes;
            2'd1: loader_read_data_q[0 +: 64] <= bandwidth_write_bytes;
            2'd2: loader_read_data_q[0 +: 64] <= bandwidth_active_cycles;
            default: loader_read_data_q[0 +: 64] <= bandwidth_stall_cycles;
          endcase
          loader_done_q <= 1'b1;
          read_probe_done_q <= 1'b1;
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= READ_PROBE_DONE;
        end else if (jtag_command_opcode == LOADER_OP_CLEAR_BANDWIDTH_COUNTERS && jtag_command_chunk == 2'd0) begin
          bandwidth_clear_q <= 1'b1;
          loader_read_data_q <= '0;
          loader_done_q <= 1'b1;
          read_probe_done_q <= 1'b1;
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= READ_PROBE_DONE;
        end else if (jtag_command_opcode == LOADER_OP_ECHO_CHUNK && jtag_command_chunk == 2'd0) begin
          loader_read_data_q <= jtag_command_chunk_data;
          loader_done_q <= 1'b1;
          read_probe_done_q <= 1'b1;
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= READ_PROBE_DONE;
        end else if (jtag_command_opcode == LOADER_OP_RUN_HOST_FULLBEAT && jtag_command_chunk == 2'd0 && WB_SEL_BITS <= 16) begin
          loader_addr_q <= jtag_command_addr_low16;
          loader_write_data_q <= jtag_command_chunk_data;
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          loader_fullbeat_read_after_write_q <= 1'b1;
          loader_fullbeat_compare_active_q <= 1'b0;
          loader_fullbeat_done_q <= 1'b0;
          loader_fullbeat_mismatch_count_q <= 7'd0;
          loader_fullbeat_addr_q <= jtag_command_addr_full;
          loader_burst_base_addr_q <= jtag_command_addr_full;
          loader_fullbeat_expected_base_q <= jtag_command_data_byte;
          loader_fullbeat_write_echo_q <= jtag_command_chunk_data[0 +: 32];
          loader_fullbeat_issue_cycle_q <= 32'd0;
          loader_fullbeat_last_write_ack_delta_q <= 4'd0;
          loader_fullbeat_last_read_ack_delta_q <= 4'd0;
          loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
          loader_fullbeat_last_issue_data_q <= '0;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_LOAD_PACKET_BEAT && jtag_command_chunk == 2'd0 && WB_SEL_BITS <= 16) begin
          loader_packet_data_q[jtag_command_addr[1:0]] <= jtag_command_chunk_data;
          loader_read_data_q <= jtag_command_chunk_data;
          loader_done_q <= 1'b1;
          read_probe_done_q <= 1'b1;
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= READ_PROBE_DONE;
        end else if (jtag_command_opcode == LOADER_OP_LOAD_PACKET_PAIR && jtag_command_chunk == 2'd0 && WB_SEL_BITS == 8) begin
          loader_packet_data_q[jtag_command_addr[1:0]] <= jtag_command_pair_data[0 +: 64];
          if (jtag_command_addr[1:0] != 2'h3)
            loader_packet_data_q[jtag_command_addr[1:0] + 2'd1] <= jtag_command_pair_data[64 +: 64];
          loader_read_data_q <= '0;
          loader_read_data_q[0 +: 64] <= jtag_command_pair_data[0 +: 64];
          read_probe_data_q[0 +: 128] <= jtag_command_pair_data;
          loader_done_q <= 1'b1;
          read_probe_done_q <= 1'b1;
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= READ_PROBE_DONE;
        end else if (jtag_command_opcode == LOADER_OP_RUN_HOST_PACKET && jtag_command_chunk == 2'd0 && WB_SEL_BITS <= 16) begin
          loader_addr_q <= jtag_command_addr_full;
          loader_write_data_q <= loader_packet_data_q[0];
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          loader_fullbeat_read_after_write_q <= TINYSTORIES_VERIFY_PACKET_WRITES;
          loader_fullbeat_compare_active_q <= 1'b0;
          loader_fullbeat_done_q <= 1'b0;
          loader_fullbeat_mismatch_count_q <= 7'd0;
          loader_fullbeat_addr_q <= jtag_command_addr_full;
          loader_burst_base_addr_q <= jtag_command_addr_full;
          loader_fullbeat_expected_base_q <= 8'h00;
          loader_fullbeat_write_echo_q <= loader_packet_data_q[0][0 +: 32];
          loader_fullbeat_issue_cycle_q <= 32'd0;
          loader_fullbeat_last_write_ack_delta_q <= 4'd0;
          loader_fullbeat_last_read_ack_delta_q <= 4'd0;
          loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
          loader_fullbeat_last_issue_data_q <= '0;
          loader_burst_active_q <= 1'b1;
          loader_burst_packet_mode_q <= 1'b1;
          loader_burst_read_phase_q <= 1'b0;
          loader_burst_count_q <= jtag_command_packet_count == 3'd0 ? 8'd0 :
            (jtag_command_packet_count > 3'd4 ? 8'd3 : {5'd0, jtag_command_packet_count} - 8'd1);
          loader_burst_index_q <= 8'd0;
          loader_burst_mismatch_count_q <= 8'd0;
          loader_burst_first_mismatch_q <= 8'hff;
          loader_packet_write_ack_seen_q <= 1'b0;
          loader_packet_read_ack_seen_q <= 1'b0;
          loader_packet_write_ack_index_q <= 8'd0;
          loader_packet_write_ack_addr_q <= '0;
          loader_packet_write_ack_data_q <= '0;
          loader_packet_write_ack_sel_q <= '0;
          loader_packet_read_ack_addr_q <= '0;
          loader_packet_read_ack_data_q <= '0;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_RUN_RTL_BURST && jtag_command_chunk == 2'd0 && WB_SEL_BITS <= 16) begin
          loader_addr_q <= jtag_command_addr_low16;
          loader_write_data_q <= generated_burst_fullbeat(8'd0);
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          loader_fullbeat_read_after_write_q <= 1'b1;
          loader_fullbeat_compare_active_q <= 1'b0;
          loader_fullbeat_done_q <= 1'b0;
          loader_fullbeat_mismatch_count_q <= 7'd0;
          loader_fullbeat_addr_q <= jtag_command_addr_low16;
          loader_burst_base_addr_q <= jtag_command_addr_low16;
          loader_fullbeat_expected_base_q <= 8'h40;
          loader_fullbeat_write_echo_q <= jtag_command_chunk_data[0 +: 32];
          loader_fullbeat_issue_cycle_q <= 32'd0;
          loader_fullbeat_last_write_ack_delta_q <= 4'd0;
          loader_fullbeat_last_read_ack_delta_q <= 4'd0;
          loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
          loader_fullbeat_last_issue_data_q <= '0;
          loader_burst_active_q <= 1'b1;
          loader_burst_packet_mode_q <= 1'b0;
          loader_burst_read_phase_q <= 1'b0;
          loader_burst_count_q <= jtag_command_data_byte == 8'd0 ? 8'd0 : jtag_command_data_byte - 8'd1;
          loader_burst_index_q <= 8'd0;
          loader_burst_mismatch_count_q <= 8'd0;
          loader_burst_first_mismatch_q <= 8'hff;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_WRITE_CHUNK && jtag_command_chunk == 2'd0 && WB_SEL_BITS <= 16) begin
          loader_addr_q <= jtag_command_addr[WB_ADDR_BITS - 1:0];
          loader_write_data_q <= jtag_command_chunk_data;
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_READ_BEAT && jtag_command_chunk == 2'd0) begin
          loader_addr_q <= jtag_command_addr[WB_ADDR_BITS - 1:0];
          loader_standalone_read_request_addr_q <= jtag_command_addr[WB_ADDR_BITS - 1:0];
          loader_standalone_read_issue_cycle_q <= 32'd0;
          loader_standalone_read_ack_delta_q <= 4'd0;
          loader_standalone_read_ack_addr_q <= '0;
          loader_standalone_read_ack_opcode_q <= 8'd0;
          loader_read_chunk_q <= 2'd0;
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_WRITE_LOWBYTE) begin
          loader_addr_q <= jtag_command_lowbyte_addr;
          loader_write_data_q <= {WB_SEL_BITS{jtag_command_data_byte}};
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          loader_lowbyte_index_q <= jtag_command_lowbyte_index;
          loader_lowbyte_addr_q <= jtag_command_addr[7:0];
          loader_lowbyte_write_data_q <= jtag_command_data_byte;
          loader_lowbyte_write_seen_q <= 1'b1;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_READ_LOWBYTE) begin
          loader_addr_q <= jtag_command_lowbyte_addr;
          loader_lowbyte_index_q <= jtag_command_lowbyte_index;
          loader_lowbyte_addr_q <= jtag_command_addr[7:0];
          loader_read_chunk_q <= 2'd0;
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_WRITE_DENSE_BYTE) begin
          loader_addr_q <= jtag_command_dense_addr;
          loader_write_data_q <= jtag_command_dense_data;
          loader_sel_q <= jtag_command_dense_sel;
          loader_dense_write_seen_q <= 1'b1;
          loader_dense_write_addr_q <= jtag_command_dense_addr[15:0];
          loader_dense_write_lane_q <= jtag_command_addr[5:0];
          loader_dense_write_data_q <= jtag_command_data_byte;
          loader_dense_write_sel_low_q <= jtag_command_dense_sel[15:0];
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_READ_DENSE_BEAT) begin
          loader_addr_q <= jtag_command_addr[WB_ADDR_BITS - 1:0];
          loader_read_chunk_q <= 2'd0;
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b0;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_RUN_AUTOPROBE) begin
          read_probe_expected_byte_q <= jtag_command_data_byte;
          read_probe_stream_base_q <= jtag_command_addr[5:0];
          read_probe_write_drain_q <= 10'd0;
          read_probe_wait_cycles_q <= 32'd0;
          read_probe_write_index_q <= 2'd0;
          read_probe_read_index_q <= 3'd0;
          read_probe_stream_bytes_q <= '0;
          read_probe_stream_valid_q <= 4'd0;
          read_probe_stream_mismatch_q <= 4'd0;
          read_probe_write_ack_seen_q <= 1'b0;
          read_probe_read_ack_seen_q <= 1'b0;
          read_probe_err_seen_q <= 1'b0;
          read_probe_stall_seen_q <= 1'b0;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= READ_PROBE_ISSUE_WRITE;
        end else if (jtag_command_opcode == LOADER_OP_RUN_HARDCODED_AUTOPROBE) begin
          read_probe_expected_byte_q <= PROBE_BYTE_VALUE;
          read_probe_stream_base_q <= jtag_command_addr[5:0];
          read_probe_write_drain_q <= 10'd0;
          read_probe_wait_cycles_q <= 32'd0;
          read_probe_write_index_q <= 2'd0;
          read_probe_read_index_q <= 3'd0;
          read_probe_stream_bytes_q <= '0;
          read_probe_stream_valid_q <= 4'd0;
          read_probe_stream_mismatch_q <= 4'd0;
          read_probe_write_ack_seen_q <= 1'b0;
          read_probe_read_ack_seen_q <= 1'b0;
          read_probe_err_seen_q <= 1'b0;
          read_probe_stall_seen_q <= 1'b0;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= READ_PROBE_ISSUE_WRITE;
        end else if (jtag_command_opcode == LOADER_OP_RUN_HARDCODED_SINGLEBYTE) begin
          read_probe_single_q <= 1'b1;
          read_probe_expected_byte_q <= hardcoded_probe_value(jtag_command_addr[9:8]);
          read_probe_stream_base_q <= jtag_command_addr[5:0];
          read_probe_write_drain_q <= 10'd0;
          read_probe_wait_cycles_q <= 32'd0;
          read_probe_write_index_q <= 2'd0;
          read_probe_read_index_q <= 3'd0;
          read_probe_stream_bytes_q <= '0;
          read_probe_stream_valid_q <= 4'd0;
          read_probe_stream_mismatch_q <= 4'd0;
          read_probe_write_ack_seen_q <= 1'b0;
          read_probe_read_ack_seen_q <= 1'b0;
          read_probe_err_seen_q <= 1'b0;
          read_probe_stall_seen_q <= 1'b0;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= READ_PROBE_ISSUE_WRITE;
        end else if (jtag_command_opcode == LOADER_OP_WRITE_DENSE_FILL) begin
          loader_addr_q <= jtag_command_addr[WB_ADDR_BITS - 1:0];
          loader_write_data_q <= {WB_SEL_BITS{jtag_command_data_byte}};
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          loader_dense_write_seen_q <= 1'b1;
          loader_dense_write_addr_q <= jtag_command_addr[15:0];
          loader_dense_write_lane_q <= 6'd0;
          loader_dense_write_data_q <= jtag_command_data_byte;
          loader_dense_write_sel_low_q <= 16'hffff;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else if (jtag_command_opcode == LOADER_OP_RUN_FULLBEAT) begin
          loader_addr_q <= jtag_command_addr_low16;
          loader_write_data_q <= jtag_command_fullbeat_data;
          loader_sel_q <= {WB_SEL_BITS{1'b1}};
          loader_fullbeat_read_after_write_q <= 1'b1;
          loader_fullbeat_compare_active_q <= 1'b0;
          loader_fullbeat_done_q <= 1'b0;
          loader_fullbeat_mismatch_count_q <= 7'd0;
          loader_fullbeat_addr_q <= jtag_command_addr_low16;
          loader_fullbeat_expected_base_q <= jtag_command_data_byte;
          loader_fullbeat_write_echo_q <= jtag_command_fullbeat_data[0 +: 32];
          loader_fullbeat_issue_cycle_q <= 32'd0;
          loader_fullbeat_last_write_ack_delta_q <= 4'd0;
          loader_fullbeat_last_read_ack_delta_q <= 4'd0;
          loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
          loader_fullbeat_last_issue_data_q <= '0;
      read_probe_single_q <= 1'b0;
          read_probe_cyc_q <= 1'b1;
          read_probe_stb_q <= 1'b1;
          read_probe_we_q <= 1'b1;
          read_probe_state_q <= LOADER_ISSUE;
        end else begin
          loader_error_q <= 1'b1;
          read_probe_state_q <= LOADER_ERROR;
        end
      end else if (
        !TINYSTORIES_LOADER_ONLY && jtag_command_event &&
        !jtag_command_accept_phase_q && read_probe_done_q
      ) begin
        loader_last_opcode_q <= jtag_command_opcode;
        loader_last_chunk_q <= jtag_command_chunk;
        loader_command_payload_addr_q <= jtag_command_addr;
        loader_last_magic_ok_q <= 1'b0;
        wb_ack_count_q <= 32'd0;
        wb_err_count_q <= 32'd0;
        wb_stall_count_q <= 32'd0;
        read_probe_state_q <= READ_PROBE_RESET;
        read_probe_cyc_q <= 1'b0;
        read_probe_stb_q <= 1'b0;
        read_probe_we_q <= 1'b0;
        read_probe_done_q <= 1'b0;
        read_probe_write_ack_seen_q <= 1'b0;
        read_probe_read_ack_seen_q <= 1'b0;
        read_probe_err_seen_q <= 1'b0;
        read_probe_stall_seen_q <= 1'b0;
        read_probe_data_q <= '0;
        read_probe_expected_byte_q <= PROBE_BYTE_VALUE;
        read_probe_stream_base_q <= (read_probe_run_count_q[5:0] + 6'd1) << 2;
        read_probe_write_drain_q <= 10'd0;
        read_probe_wait_cycles_q <= 32'd0;
        read_probe_write_index_q <= 2'd0;
        read_probe_read_index_q <= 3'd0;
        read_probe_stream_bytes_q <= '0;
        read_probe_stream_valid_q <= 4'd0;
        read_probe_stream_mismatch_q <= 4'd0;
        read_probe_run_count_q <= read_probe_run_count_q + 16'd1;
      end else begin
        case (read_probe_state_q)
        READ_PROBE_RESET: begin
          read_probe_single_q <= 1'b0;
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_done_q <= 1'b0;
          read_probe_write_ack_seen_q <= 1'b0;
          read_probe_read_ack_seen_q <= 1'b0;
          read_probe_err_seen_q <= 1'b0;
          read_probe_stall_seen_q <= 1'b0;
          read_probe_write_drain_q <= 10'd0;
          read_probe_wait_cycles_q <= 32'd0;
          read_probe_write_index_q <= 2'd0;
          read_probe_read_index_q <= 3'd0;
          read_probe_stream_bytes_q <= '0;
          read_probe_stream_valid_q <= 4'd0;
          read_probe_stream_mismatch_q <= 4'd0;
          read_probe_state_q <= READ_PROBE_WAIT_CALIB;
        end

        READ_PROBE_WAIT_CALIB: begin
          // Calibration may complete during READ_PROBE_RESET before this
          // state reaches WAIT_CALIB.  calib_seen_q is the sticky observation
          // in this clock domain; relying only on the raw indication leaves
          // the FSM parked forever and PCIe never observes boot_done.
          if (calib_complete || calib_seen_q || ddr_ready_q) begin
            if (BOOT_ISOLATE_UNTIL_CALIB != 0) begin
              read_probe_cyc_q <= 1'b0;
              read_probe_stb_q <= 1'b0;
              read_probe_we_q <= 1'b0;
              read_probe_done_q <= 1'b1;
              read_probe_state_q <= READ_PROBE_DONE;
            end else begin
              read_probe_cyc_q <= 1'b1;
              read_probe_stb_q <= 1'b1;
              read_probe_we_q <= 1'b1;
              read_probe_state_q <= READ_PROBE_ISSUE_WRITE;
            end
          end
        end

        READ_PROBE_ISSUE_WRITE: begin
          if (wb_stall) begin
            read_probe_stall_seen_q <= 1'b1;
            read_probe_wait_cycles_q <= read_probe_wait_cycles_q + 32'd1;
          end else begin
            read_probe_stb_q <= 1'b0;
            read_probe_state_q <= wb_ack ? READ_PROBE_ISSUE_READ : READ_PROBE_WAIT_WRITE_ACK;
          end
          if (wb_err) begin
            read_probe_err_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_DONE;
          end
          if (wb_ack) begin
            read_probe_write_ack_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_stb_q <= 1'b0;
            read_probe_we_q <= 1'b0;
            read_probe_write_drain_q <= 10'd0;
            read_probe_state_q <= READ_PROBE_WAIT_WRITE_DRAIN;
          end
        end

        READ_PROBE_WAIT_WRITE_ACK: begin
          read_probe_wait_cycles_q <= read_probe_wait_cycles_q + 32'd1;
          if (wb_err) begin
            read_probe_err_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_DONE;
          end else if (wb_ack) begin
            read_probe_write_ack_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_stb_q <= 1'b0;
            read_probe_we_q <= 1'b0;
            read_probe_write_drain_q <= 10'd0;
            read_probe_state_q <= READ_PROBE_WAIT_WRITE_DRAIN;
          end
        end

        READ_PROBE_WAIT_WRITE_DRAIN: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_wait_cycles_q <= read_probe_wait_cycles_q + 32'd1;
          if (read_probe_write_drain_q == 10'h3ff) begin
            read_probe_state_q <= READ_PROBE_NEXT_WRITE;
          end else begin
            read_probe_write_drain_q <= read_probe_write_drain_q + 10'd1;
          end
        end

        READ_PROBE_NEXT_WRITE: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          if (read_probe_single_q || read_probe_write_index_q == 2'd3) begin
            read_probe_read_index_q <= 3'd0;
            read_probe_cyc_q <= 1'b1;
            read_probe_stb_q <= 1'b1;
            read_probe_we_q <= 1'b0;
            read_probe_state_q <= READ_PROBE_ISSUE_READ;
          end else begin
            read_probe_write_index_q <= read_probe_write_index_q + 2'd1;
            read_probe_cyc_q <= 1'b1;
            read_probe_stb_q <= 1'b1;
            read_probe_we_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_ISSUE_WRITE;
          end
        end

        READ_PROBE_ISSUE_READ: begin
          read_probe_we_q <= 1'b0;
          read_probe_stb_q <= 1'b1;
          if (wb_stall) begin
            read_probe_stall_seen_q <= 1'b1;
            read_probe_wait_cycles_q <= read_probe_wait_cycles_q + 32'd1;
          end else begin
            read_probe_stb_q <= 1'b0;
            read_probe_state_q <= wb_ack ? READ_PROBE_DONE : READ_PROBE_WAIT_READ_ACK;
          end
          if (wb_err) begin
            read_probe_err_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_DONE;
          end
          if (wb_ack) begin
            read_probe_read_ack_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_data_q <= wb_data;
            if (read_probe_single_q || read_probe_read_index_q != 3'd0) begin
              read_probe_stream_bytes_q[read_probe_capture_index * 8 +: 8] <=
                read_probe_capture_byte;
              read_probe_stream_valid_q[read_probe_capture_index] <= 1'b1;
              read_probe_stream_mismatch_q[read_probe_capture_index] <=
                read_probe_capture_byte !=
                (read_probe_expected_byte_q +
                 (read_probe_single_q ? 8'd0 : read_probe_stream_base_q) +
                 (read_probe_single_q ? 8'd0 : {6'd0, read_probe_capture_index}));
            end
            read_probe_state_q <= READ_PROBE_NEXT_READ;
          end
        end

        READ_PROBE_WAIT_READ_ACK: begin
          read_probe_wait_cycles_q <= read_probe_wait_cycles_q + 32'd1;
          if (wb_err) begin
            read_probe_err_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_DONE;
          end else if (wb_ack) begin
            read_probe_read_ack_seen_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_data_q <= wb_data;
            if (read_probe_single_q || read_probe_read_index_q != 3'd0) begin
              read_probe_stream_bytes_q[read_probe_capture_index * 8 +: 8] <=
                read_probe_capture_byte;
              read_probe_stream_valid_q[read_probe_capture_index] <= 1'b1;
              read_probe_stream_mismatch_q[read_probe_capture_index] <=
                read_probe_capture_byte !=
                (read_probe_expected_byte_q +
                 (read_probe_single_q ? 8'd0 : read_probe_stream_base_q) +
                 (read_probe_single_q ? 8'd0 : {6'd0, read_probe_capture_index}));
            end
            read_probe_state_q <= READ_PROBE_NEXT_READ;
          end
        end

        READ_PROBE_NEXT_READ: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          if (read_probe_single_q || read_probe_read_index_q == 3'd4) begin
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_DONE;
          end else begin
            read_probe_read_index_q <= read_probe_read_index_q + 3'd1;
            read_probe_cyc_q <= 1'b1;
            read_probe_stb_q <= 1'b1;
            read_probe_we_q <= 1'b0;
            read_probe_state_q <= READ_PROBE_ISSUE_READ;
          end
        end

        READ_PROBE_DONE: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_done_q <= 1'b1;
        end

        LOADER_ISSUE: begin
          if (read_probe_is_loader_beat && !read_probe_we_q && !wb_stall) begin
            loader_standalone_read_issue_cycle_q <= cycle_count_q;
          end
          if (
            read_probe_is_loader_beat &&
            !wb_stall &&
            loader_fullbeat_issue_phase_q == FULLBEAT_PHASE_NONE &&
            (loader_fullbeat_read_after_write_q || loader_fullbeat_compare_active_q)
          ) begin
            loader_fullbeat_issue_phase_q <=
              loader_fullbeat_read_after_write_q ? FULLBEAT_PHASE_WRITE : FULLBEAT_PHASE_READ;
            loader_fullbeat_issue_cycle_q <= cycle_count_q;
            loader_fullbeat_last_issue_data_q <= wb_data_to_controller[127:0];
          end
          if (wb_stall) begin
            loader_stall_seen_q <= 1'b1;
            loader_wait_cycles_q <= loader_wait_cycles_q + 32'd1;
          end else begin
            read_probe_stb_q <= 1'b0;
            read_probe_state_q <= wb_ack ? READ_PROBE_DONE : LOADER_WAIT_ACK;
          end
          if (wb_err) begin
            loader_error_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_stb_q <= 1'b0;
            read_probe_we_q <= 1'b0;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= LOADER_ERROR;
            loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
          end
          if (wb_ack) begin
            read_probe_cyc_q <= 1'b0;
            read_probe_stb_q <= 1'b0;
            if (read_probe_we_q) begin
              loader_write_ack_seen_q <= 1'b1;
              if (loader_burst_active_q && loader_burst_packet_mode_q) begin
                wb_packet_write_ack_count_q <= wb_packet_write_ack_count_q + 32'd1;
                loader_packet_write_ack_seen_q <= 1'b1;
                loader_packet_write_ack_index_q <= loader_burst_index_q;
                loader_packet_write_ack_addr_q <= loader_addr_q;
                loader_packet_write_ack_data_q <= wb_data_to_controller;
                loader_packet_write_ack_sel_q <= wb_sel_to_controller;
              end
              if (loader_fullbeat_issue_phase_q == FULLBEAT_PHASE_WRITE) begin
                loader_fullbeat_last_write_ack_delta_q <=
                  clamp_delta4(loader_fullbeat_issue_cycle_q, cycle_count_q);
                loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
              end
              read_probe_write_drain_q <= 10'd0;
              read_probe_state_q <= LOADER_WRITE_DRAIN;
            end else begin
              loader_read_ack_seen_q <= 1'b1;
              loader_read_data_q <= wb_data;
              if (loader_burst_active_q && loader_burst_packet_mode_q) begin
                wb_packet_read_ack_count_q <= wb_packet_read_ack_count_q + 32'd1;
                loader_packet_read_ack_seen_q <= 1'b1;
                loader_packet_read_ack_addr_q <= loader_addr_q;
                loader_packet_read_ack_data_q <= wb_data;
              end
              loader_standalone_read_ack_addr_q <= loader_addr_q;
              loader_standalone_read_ack_opcode_q <= loader_last_opcode_q;
              loader_standalone_read_ack_delta_q <=
                clamp_delta4(loader_standalone_read_issue_cycle_q, cycle_count_q);
              if (loader_last_opcode_q == LOADER_OP_READ_LOWBYTE) begin
                loader_lowbyte_read_data_q <= wb_data[loader_lowbyte_index_q * 8 +: 8];
                loader_lowbyte_read_seen_q <= 1'b1;
              end
              if (loader_fullbeat_issue_phase_q == FULLBEAT_PHASE_READ) begin
                loader_fullbeat_last_read_ack_delta_q <=
                  clamp_delta4(loader_fullbeat_issue_cycle_q, cycle_count_q);
                loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
              end
              if (loader_fullbeat_compare_active_q) begin
                loader_fullbeat_done_q <= 1'b1;
                loader_fullbeat_mismatch_count_q <= loader_fullbeat_mismatch_count;
                loader_fullbeat_compare_active_q <= 1'b0;
                if (loader_burst_active_q && loader_fullbeat_mismatch_count != 7'd0) begin
                  loader_burst_mismatch_count_q <= loader_burst_mismatch_count_q + 8'd1;
                  loader_any_mismatch_q <= 1'b1;
                  if (loader_burst_first_mismatch_q == 8'hff)
                    loader_burst_first_mismatch_q <= loader_burst_index_q;
                end
              end
              if (loader_burst_active_q) begin
                read_probe_state_q <= LOADER_BURST_NEXT;
              end else if (loader_last_opcode_q == LOADER_OP_RUN_HOST_FULLBEAT) begin
                loader_command_cooldown_q <= LOADER_HOST_FULLBEAT_COMMAND_COOLDOWN;
                read_probe_state_q <= LOADER_COMMAND_COOLDOWN;
              end else begin
                loader_done_q <= 1'b1;
                read_probe_done_q <= 1'b1;
                read_probe_state_q <= READ_PROBE_DONE;
              end
            end
          end
        end

        LOADER_WAIT_ACK: begin
          loader_wait_cycles_q <= loader_wait_cycles_q + 32'd1;
          if (wb_err) begin
            loader_error_q <= 1'b1;
            read_probe_cyc_q <= 1'b0;
            read_probe_stb_q <= 1'b0;
            read_probe_we_q <= 1'b0;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= LOADER_ERROR;
            loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
          end else if (wb_ack) begin
            read_probe_cyc_q <= 1'b0;
            if (read_probe_we_q) begin
              loader_write_ack_seen_q <= 1'b1;
              if (loader_burst_active_q && loader_burst_packet_mode_q) begin
                wb_packet_write_ack_count_q <= wb_packet_write_ack_count_q + 32'd1;
                loader_packet_write_ack_seen_q <= 1'b1;
                loader_packet_write_ack_index_q <= loader_burst_index_q;
                loader_packet_write_ack_addr_q <= loader_addr_q;
                loader_packet_write_ack_data_q <= wb_data_to_controller;
                loader_packet_write_ack_sel_q <= wb_sel_to_controller;
              end
              if (loader_fullbeat_issue_phase_q == FULLBEAT_PHASE_WRITE) begin
                loader_fullbeat_last_write_ack_delta_q <=
                  clamp_delta4(loader_fullbeat_issue_cycle_q, cycle_count_q);
                loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
              end
              read_probe_write_drain_q <= 10'd0;
              read_probe_state_q <= LOADER_WRITE_DRAIN;
            end else begin
              loader_read_ack_seen_q <= 1'b1;
              loader_read_data_q <= wb_data;
              if (loader_burst_active_q && loader_burst_packet_mode_q) begin
                wb_packet_read_ack_count_q <= wb_packet_read_ack_count_q + 32'd1;
                loader_packet_read_ack_seen_q <= 1'b1;
                loader_packet_read_ack_addr_q <= loader_addr_q;
                loader_packet_read_ack_data_q <= wb_data;
              end
              loader_standalone_read_ack_addr_q <= loader_addr_q;
              loader_standalone_read_ack_opcode_q <= loader_last_opcode_q;
              loader_standalone_read_ack_delta_q <=
                clamp_delta4(loader_standalone_read_issue_cycle_q, cycle_count_q);
              if (loader_last_opcode_q == LOADER_OP_READ_LOWBYTE) begin
                loader_lowbyte_read_data_q <= wb_data[loader_lowbyte_index_q * 8 +: 8];
                loader_lowbyte_read_seen_q <= 1'b1;
              end
              if (loader_fullbeat_issue_phase_q == FULLBEAT_PHASE_READ) begin
                loader_fullbeat_last_read_ack_delta_q <=
                  clamp_delta4(loader_fullbeat_issue_cycle_q, cycle_count_q);
                loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
              end
              if (loader_fullbeat_compare_active_q) begin
                loader_fullbeat_done_q <= 1'b1;
                loader_fullbeat_mismatch_count_q <= loader_fullbeat_mismatch_count;
                loader_fullbeat_compare_active_q <= 1'b0;
                if (loader_burst_active_q && loader_fullbeat_mismatch_count != 7'd0) begin
                  loader_burst_mismatch_count_q <= loader_burst_mismatch_count_q + 8'd1;
                  loader_any_mismatch_q <= 1'b1;
                  if (loader_burst_first_mismatch_q == 8'hff)
                    loader_burst_first_mismatch_q <= loader_burst_index_q;
                end
              end
              if (loader_burst_active_q) begin
                read_probe_state_q <= LOADER_BURST_NEXT;
              end else if (loader_last_opcode_q == LOADER_OP_RUN_HOST_FULLBEAT) begin
                loader_command_cooldown_q <= LOADER_HOST_FULLBEAT_COMMAND_COOLDOWN;
                read_probe_state_q <= LOADER_COMMAND_COOLDOWN;
              end else begin
                loader_done_q <= 1'b1;
                read_probe_done_q <= 1'b1;
                read_probe_state_q <= READ_PROBE_DONE;
              end
            end
          end
        end

        LOADER_WRITE_DRAIN: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          loader_wait_cycles_q <= loader_wait_cycles_q + 32'd1;
          if (read_probe_write_drain_q == 10'h3ff) begin
            if (loader_fullbeat_read_after_write_q) begin
              loader_fullbeat_read_after_write_q <= 1'b0;
              loader_fullbeat_compare_active_q <= 1'b1;
              loader_addr_q <= loader_fullbeat_addr_q;
              loader_sel_q <= {WB_SEL_BITS{1'b1}};
              read_probe_cyc_q <= 1'b1;
              read_probe_stb_q <= 1'b1;
              read_probe_we_q <= 1'b0;
              read_probe_state_q <= LOADER_ISSUE;
            end else if (loader_burst_active_q) begin
              // Advance a packet burst when write/readback verification is
              // explicitly disabled for the specialized TinyStories target.
              read_probe_state_q <= LOADER_BURST_NEXT;
            end else begin
              loader_done_q <= 1'b1;
              read_probe_done_q <= 1'b1;
              read_probe_state_q <= READ_PROBE_DONE;
            end
          end else begin
            read_probe_write_drain_q <= read_probe_write_drain_q + 10'd1;
          end
        end

        LOADER_BURST_NEXT: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          loader_wait_cycles_q <= loader_wait_cycles_q + 32'd1;
          if (loader_burst_index_q == loader_burst_count_q) begin
            loader_burst_active_q <= 1'b0;
            loader_done_q <= 1'b1;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_DONE;
          end else begin
            loader_burst_index_q <= loader_burst_index_q + 8'd1;
            loader_addr_q <= loader_burst_base_addr_q + {{(WB_ADDR_BITS - 8){1'b0}}, loader_burst_index_q + 8'd1};
            loader_fullbeat_addr_q <= loader_burst_base_addr_q + {{(WB_ADDR_BITS - 8){1'b0}}, loader_burst_index_q + 8'd1};
            loader_write_data_q <= loader_burst_packet_mode_q ?
              loader_packet_data_q[loader_burst_index_q[1:0] + 2'd1] :
              generated_burst_fullbeat(loader_burst_index_q + 8'd1);
            loader_sel_q <= {WB_SEL_BITS{1'b1}};
            loader_fullbeat_expected_base_q <= 8'h40 + loader_burst_index_q + 8'd1;
            loader_fullbeat_read_after_write_q <= TINYSTORIES_VERIFY_PACKET_WRITES;
            loader_fullbeat_compare_active_q <= 1'b0;
            loader_fullbeat_issue_phase_q <= FULLBEAT_PHASE_NONE;
            read_probe_cyc_q <= 1'b1;
            read_probe_stb_q <= 1'b1;
            read_probe_we_q <= 1'b1;
            read_probe_state_q <= LOADER_ISSUE;
          end
        end

        LOADER_COMMAND_COOLDOWN: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          loader_wait_cycles_q <= loader_wait_cycles_q + 32'd1;
          if (loader_command_cooldown_q == 16'd0) begin
            loader_done_q <= 1'b1;
            read_probe_done_q <= 1'b1;
            read_probe_state_q <= READ_PROBE_DONE;
          end else begin
            loader_command_cooldown_q <= loader_command_cooldown_q - 16'd1;
          end
        end

        LOADER_ERROR: begin
          read_probe_cyc_q <= 1'b0;
          read_probe_stb_q <= 1'b0;
          read_probe_we_q <= 1'b0;
          read_probe_done_q <= 1'b1;
        end

        default: read_probe_state_q <= READ_PROBE_DONE;
        endcase
      end
    end
  end

  logic [JTAG_DEBUG_WIDTH - 1:0] jtag_debug_payload;
  localparam int JTAG_BOOT_DEBUG_WIDTH = 336;
  logic [JTAG_BOOT_DEBUG_WIDTH - 1:0] jtag_boot_debug_payload;

  assign jtag_boot_debug_payload = jtag_debug_payload[JTAG_BOOT_DEBUG_WIDTH - 1:0];

  always_comb begin
    jtag_debug_payload = '0;
    jtag_debug_payload[0 +: 32] = JTAG_DEBUG_MAGIC;
    jtag_debug_payload[32 +: 8] = JTAG_DEBUG_VERSION;
    jtag_debug_payload[40 +: 8] = {
      1'b0,
      uart_tx,
      wb2_ack,
      wb2_stall,
      wb_err,
      wb_ack,
      calib_seen_q,
      calib_complete
    };
    jtag_debug_payload[47] = mmcm_locked;
    jtag_debug_payload[48 +: 32] = cycle_count_q;
    jtag_debug_payload[80 +: 32] = calib_seen_cycle_q;
    // The TinyStories PCIe image exposes operational status through PCIe and
    // does not consume this wide BIST debug field.  Keeping it out of the
    // controller-clock payload cone avoids routing debug1 through rowstream
    // control logic; generic/JTAG BIST images retain the diagnostic field.
    jtag_debug_payload[112 +: 32] = TINYSTORIES_LOADER_ONLY ? 32'd0 : debug1;
    jtag_debug_payload[144 +: 32] = wb_ack_count_q;
    jtag_debug_payload[176 +: 32] = wb_err_count_q;
    jtag_debug_payload[208 +: 32] = wb_stall_count_q;
    jtag_debug_payload[240 +: 32] =
      read_probe_done_q &&
      (loader_last_opcode_q == LOADER_OP_RUN_RTL_BURST ||
       loader_last_opcode_q == LOADER_OP_RUN_HOST_PACKET) ?
      {loader_burst_first_mismatch_q, loader_burst_mismatch_count_q, loader_burst_count_q, loader_burst_index_q} :
      read_probe_done_q && loader_last_opcode_q == LOADER_OP_RUN_FULLBEAT ?
      loader_read_data_q[31:0] :
      read_probe_done_q && loader_last_opcode_q == LOADER_OP_RUN_HARDCODED_SINGLEBYTE ?
      {8'd0, read_probe_expected_byte_q, read_probe_stream_mismatch_q,
       read_probe_stream_valid_q, read_probe_stream_bytes_q[7:0]} :
      read_probe_done_q &&
      (loader_last_opcode_q == LOADER_OP_WRITE_LOWBYTE ||
       loader_last_opcode_q == LOADER_OP_READ_LOWBYTE) ?
      {loader_lowbyte_addr_q, loader_lowbyte_write_data_q,
       loader_lowbyte_read_data_q, 6'd0, loader_lowbyte_read_seen_q,
       loader_lowbyte_write_seen_q} :
      read_probe_done_q ? loader_read_data_q[31:0] : read_probe_data_q[31:0];
    jtag_debug_payload[272 +: 32] =
      {jtag_command_count[7:0], loader_last_opcode_q,
       6'd0, loader_last_chunk_q, loader_last_magic_ok_q, loader_last_accepted_q};
    jtag_debug_payload[304 +: 32] = {
      7'd0,
      loader_fullbeat_mismatch_count_q,
      loader_fullbeat_done_q,
      read_probe_done_q && (read_probe_stream_mismatch_q != 4'd0),
      read_probe_stall_seen_q,
      read_probe_err_seen_q,
      read_probe_read_ack_seen_q,
      read_probe_write_ack_seen_q,
      read_probe_done_q,
      loader_stall_seen_q,
      loader_error_q,
      loader_read_ack_seen_q,
      loader_write_ack_seen_q,
      loader_done_q,
      read_probe_cyc_q,
      read_probe_stb_q,
      loader_debug_state
    };
    jtag_debug_payload[336 +: 128] = loader_last_opcode_q == LOADER_OP_RUN_HOST_PACKET ?
      loader_packet_write_ack_data_q[0 +: 128] : loader_read_data_q[0 +: 128];
    jtag_debug_payload[464] = loader_last_opcode_q == LOADER_OP_RUN_HOST_PACKET ?
      loader_packet_write_ack_seen_q :
      loader_last_opcode_q == LOADER_OP_READ_BEAT ?
      loader_read_ack_seen_q : loader_fullbeat_done_q;
    jtag_debug_payload[465 +: 7] = loader_last_opcode_q == LOADER_OP_RUN_HOST_PACKET ?
      {loader_packet_write_ack_index_q[5:0], loader_packet_read_ack_seen_q} :
      loader_last_opcode_q == LOADER_OP_READ_BEAT ?
      loader_standalone_read_ack_opcode_q[6:0] : loader_fullbeat_mismatch_count_q;
    jtag_debug_payload[472 +: 24] = loader_last_opcode_q == LOADER_OP_RUN_RTL_BURST ?
      {8'd0, loader_burst_mismatch_count_q, loader_burst_first_mismatch_q} :
      loader_last_opcode_q == LOADER_OP_RUN_HOST_PACKET ?
      loader_packet_write_ack_addr_q[23:0] :
      loader_last_opcode_q == LOADER_OP_READ_BEAT ?
      loader_standalone_read_ack_addr_q[23:0] :
      loader_fullbeat_addr_q[23:0];
    jtag_debug_payload[496 +: 8] = loader_last_opcode_q == LOADER_OP_RUN_RTL_BURST ?
      loader_burst_count_q :
      loader_last_opcode_q == LOADER_OP_RUN_HOST_PACKET ?
      loader_packet_write_ack_sel_q[7:0] :
      loader_last_opcode_q == LOADER_OP_READ_BEAT ?
      loader_standalone_read_request_addr_q[7:0] : loader_fullbeat_expected_base_q;
    jtag_debug_payload[504 +: 4] = loader_last_opcode_q == LOADER_OP_READ_BEAT ?
      loader_standalone_read_ack_delta_q : loader_fullbeat_last_write_ack_delta_q;
    jtag_debug_payload[508 +: 4] = loader_fullbeat_last_read_ack_delta_q;
    if (!read_probe_done_q)
      jtag_debug_payload[240 +: 32] = read_probe_stream_bytes_q;
`ifdef TASK6_TINYSTORIES_JTAG_BRIDGE
    jtag_debug_payload = tinystories_bridge_result_payload;
    // Before inference starts, retain the loader's packet readback evidence in
    // the same 512-bit USER1 payload.  This makes a completed model transfer
    // auditable without changing the accelerator interface.  Once the bridge
    // has collected a token, preserve its normal token payload.
    if (read_probe_done_q &&
        loader_last_opcode_q == LOADER_OP_RUN_HOST_PACKET &&
        tinystories_bridge_result_payload[63:32] == 32'd0) begin
      jtag_debug_payload[256 +: 32] = {
        {8{loader_any_mismatch_q}},
        loader_burst_mismatch_count_q,
        loader_burst_count_q,
        loader_burst_index_q
      };
    end
    // The specialized TinyStories image disables packet write/readback
    // verification for timing.  Preserve a real standalone dense-beat read
    // in USER1 so the loaded model bytes can be compared independently of
    // inference and of the synthetic packet diagnostic above.
    if (read_probe_done_q &&
        loader_last_opcode_q == LOADER_OP_READ_DENSE_BEAT &&
        tinystories_bridge_result_payload[63:32] == 32'd0) begin
      jtag_debug_payload[336 +: 128] = loader_read_data_q[0 +: 128];
      jtag_debug_payload[464] = loader_read_ack_seen_q;
      jtag_debug_payload[472 +: 24] = loader_standalone_read_ack_addr_q[23:0];
      jtag_debug_payload[496 +: 8] = loader_standalone_read_request_addr_q[7:0];
    end
`endif
  end

  task6_wishbone_bandwidth_counters #(
    .SEL_BITS(WB_SEL_BITS)
  ) bandwidth_counters (
    .clk_i(controller_clk),
    .rst_ni(rst_n),
    .clear_i(bandwidth_clear_q),
    .cyc_i(memory_wb_cyc_to_controller),
    .stb_i(memory_wb_stb_to_controller),
    .we_i(memory_wb_we_to_controller),
    .sel_i(memory_wb_sel_to_controller),
    .ack_i(memory_wb_ack),
    .read_bytes_o(bandwidth_read_bytes),
    .write_bytes_o(bandwidth_write_bytes),
    .active_cycles_o(bandwidth_active_cycles),
    .stall_cycles_o(bandwidth_stall_cycles)
  );

  ddr3_top #(
    .CONTROLLER_CLK_PERIOD(CONTROLLER_CLK_PERIOD_PS),
    .DDR3_CLK_PERIOD(DDR3_CLK_PERIOD_PS),
    .ROW_BITS(ROW_BITS),
    .COL_BITS(COL_BITS),
    .BA_BITS(BA_BITS),
    .BYTE_LANES(BYTE_LANES),
    .AUX_WIDTH(4),
    .WB2_ADDR_BITS(7),
    .WB2_DATA_BITS(32),
    .DUAL_RANK_DIMM(0),
    .SPEED_BIN(SPEED_BIN_PARAM),
    .SDRAM_CAPACITY(SDRAM_CAPACITY_PARAM),
    .TRCD(13_750),
    .TRP(13_750),
    .TRAS(35_000),
    .ODELAY_SUPPORTED(0),
    .SECOND_WISHBONE(0),
    .DLL_OFF(DLL_OFF_PARAM),
    .WB_ERROR(0),
    .BIST_MODE(BIST_MODE_PARAM),
    .BIST_TEST_DATAMASK(BIST_TEST_DATAMASK),
    .ECC_ENABLE(0)
  ) uberddr3 (
    .i_controller_clk(controller_clk),
    .i_ddr3_clk(ddr3_clk),
    .i_ref_clk(ref_clk),
    .i_ddr3_clk_90(ddr3_clk_90),
    .i_rst_n(rst_n),
    .i_wb_cyc(memory_wb_cyc_to_controller),
    .i_wb_stb(memory_wb_stb_to_controller),
    .i_wb_we(memory_wb_we_to_controller),
    .i_wb_addr(memory_wb_addr_to_controller),
    .i_wb_data(memory_wb_data_to_controller),
    .i_wb_sel(memory_wb_sel_to_controller),
    .i_aux(memory_wb_we_to_controller ? 4'd0 : 4'd1),
    .o_wb_stall(memory_wb_stall),
    .o_wb_ack(memory_wb_ack),
    .o_wb_err(memory_wb_err),
    .o_wb_data(memory_wb_data),
    .o_aux(wb_aux),
    .i_wb2_cyc(1'b0),
    .i_wb2_stb(1'b0),
    .i_wb2_we(1'b0),
    .i_wb2_addr(7'd0),
    .i_wb2_data(32'd0),
    .i_wb2_sel(4'd0),
    .o_wb2_stall(wb2_stall),
    .o_wb2_ack(wb2_ack),
    .o_wb2_data(wb2_data),
    .o_ddr3_clk_p(ddr3_clk_p_w),
    .o_ddr3_clk_n(ddr3_clk_n_w),
    .o_ddr3_reset_n(ddram_reset_n),
    .o_ddr3_cke(ddr3_cke_w),
    .o_ddr3_cs_n(ddr3_cs_n_w),
    .o_ddr3_ras_n(ddram_ras_n),
    .o_ddr3_cas_n(ddram_cas_n),
    .o_ddr3_we_n(ddram_we_n),
    .o_ddr3_addr(ddram_a),
    .o_ddr3_ba_addr(ddram_ba),
    .io_ddr3_dq(ddram_dq),
    .io_ddr3_dqs(ddram_dqs_p),
    .io_ddr3_dqs_n(ddram_dqs_n),
    .o_ddr3_dm(ddr3_dm_w),
    .o_ddr3_odt(ddr3_odt_w),
    .o_calib_complete(calib_complete),
    .o_debug1(debug1),
    .i_user_self_refresh(1'b0),
    .uart_tx(uart_tx)
  );

  generate
    if (!DISABLE_JTAG_DEBUG_SHIFT) begin : g_debug_shift_enabled
      task6_uberddr3_jtag_debug_shift #(
        .WIDTH(JTAG_DEBUG_WIDTH),
        .JTAG_CHAIN(JTAG_CHAIN),
        .DISABLE_JTAG(DISABLE_JTAG_DEBUG_SHIFT)
      ) jtag_debug_shift (
        .payload_i(jtag_debug_payload)
      );
    end else begin : g_debug_boot_status_disabled
      // PCIe TinyStories builds expose status through PCIe; no JTAG shifter
      // is needed in this configuration, avoiding a wide controller-clock
      // debug fanout. Other targets retain the full JTAG path by leaving
      // DISABLE_JTAG_DEBUG_SHIFT at its default value.
    end
  endgenerate


`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
  generate
    if (ENABLE_PCIE_TOP1) begin : gen_pcie_top1
      assign top1_start_accepted =
        pcie_top1_start_i && !top1_reset_active && !top1_reader_busy &&
        read_probe_done_q && ddr_ready_q;
      assign top1_start_rejected =
        pcie_top1_start_i && (top1_reset_active || top1_reader_busy || !read_probe_done_q ||
        !ddr_ready_q);

      task6_ddr3_rowstream_wb_top1_reader #(
        .HIDDEN_SIZE(64),
        .VOCAB_SIZE(50257),
        .ROW_BYTES(68),
        .WB_ADDR_BITS(WB_ADDR_BITS),
        .WB_DATA_BITS(WB_DATA_BITS),
        .WB_SEL_BITS(WB_SEL_BITS),
        .REVERSE_WB_BEAT_BYTES(1'b0)
      ) top1_reader (
        .clk_i(controller_clk),
        .rst_ni(rst_n && !top1_reset_active),
        .start_i(top1_start_accepted),
        .busy_o(top1_reader_busy),
        .done_o(top1_reader_done),
        .error_o(top1_reader_error),
        .wb_cyc_o(top1_reader_wb_cyc),
        .wb_stb_o(top1_reader_wb_stb),
        .wb_we_o(top1_reader_wb_we),
        .wb_addr_o(top1_reader_wb_addr),
        .wb_data_o(top1_reader_wb_data),
        .wb_sel_o(top1_reader_wb_sel),
        .wb_stall_i(wb_stall),
        .wb_ack_i(wb_ack && top1_reader_wb_cyc),
        .wb_err_i(wb_err && top1_reader_wb_cyc),
        .wb_data_i(wb_data),
        .row_valid_o(top1_row_valid),
        .row_ready_i(top1_row_ready),
        .row_token_id_o(top1_row_token_id),
        .row_weight_q_i8_o(top1_row_weight_q_i8),
        .row_sidecar_word_o(top1_row_sidecar_word),
        .row_last_o(top1_row_last),
        .debug_first_row_sidecar_beat_o(top1_debug_first_row_sidecar_beat),
        .debug_first_row_sidecar_beat_valid_o(top1_debug_first_row_sidecar_beat_valid)
      );

      task6_ddr3_rowstream_top1_cutout #(
        .HIDDEN_SIZE(64)
      ) top1_cutout (
        .clock(controller_clk),
        .reset(!rst_n || top1_reset_active),
        .row_valid(top1_row_valid),
        .row_ready(top1_row_ready),
        .row_token_id(top1_row_token_id),
        .row_weight_q_i8(top1_row_weight_q_i8),
        .row_sidecar_word(top1_row_sidecar_word),
        .row_last(top1_row_last),
        .hidden_q_i8(pcie_top1_hidden_vector_i),
        .out_valid(top1_cutout_valid),
        .out_done(top1_cutout_done),
        .out_busy(top1_cutout_busy),
        .out_error_reserved_bits(top1_cutout_error_reserved_bits),
        .out_top_token_id(top1_cutout_token_id),
        .out_top_score_signed_q024(top1_cutout_score_q024),
        .out_rows_scanned(top1_cutout_rows_scanned),
        .out_cycle_count(top1_cutout_cycle_count)
      );
    end else begin : gen_no_pcie_top1
      assign top1_start_accepted = 1'b0;
      assign top1_start_rejected = pcie_top1_start_i;
      assign top1_reader_busy = 1'b0;
      assign top1_reader_done = 1'b0;
      assign top1_reader_error = 1'b0;
      assign top1_reader_wb_cyc = 1'b0;
      assign top1_reader_wb_stb = 1'b0;
      assign top1_reader_wb_we = 1'b0;
      assign top1_reader_wb_addr = '0;
      assign top1_reader_wb_data = '0;
      assign top1_reader_wb_sel = '0;
      assign top1_row_valid = 1'b0;
      assign top1_row_token_id = 16'd0;
      assign top1_row_weight_q_i8 = 512'd0;
      assign top1_row_sidecar_word = 32'd0;
      assign top1_row_last = 1'b0;
      assign top1_debug_first_row_sidecar_beat = 64'd0;
      assign top1_debug_first_row_sidecar_beat_valid = 1'b0;
      assign top1_cutout_valid = 1'b0;
      assign top1_cutout_done = 1'b0;
      assign top1_cutout_busy = 1'b0;
      assign top1_cutout_error_reserved_bits = 1'b0;
      assign top1_cutout_token_id = 16'd0;
      assign top1_cutout_score_q024 = 46'sd0;
      assign top1_cutout_rows_scanned = 32'd0;
      assign top1_cutout_cycle_count = 32'd0;
    end
  endgenerate
`endif

  task6_uberddr3_loader_jtag_command_shift #(
    .WIDTH(JTAG_COMMAND_WIDTH),
    .JTAG_CHAIN(JTAG_COMMAND_CHAIN)
  ) jtag_command_shift (
    .controller_clk_i(controller_clk),
    .rst_ni(rst_n),
    .payload_o(jtag_command_payload_from_shift),
    .event_o(jtag_command_event_from_shift),
    .command_count_o(jtag_command_count)
  );

`ifdef TASK6_PCIE_ROWSTREAM_INGRESS_PORTS
  assign pcie_controller_clk_o = controller_clk;
  assign pcie_controller_rst_n_o = rst_n;
  // Export the already-registered readiness boundary for TinyStories.  The
  // PCIe host only needs a stable indication that DDR is usable; keeping the
  // raw MIG calibration net out of the PCIe status cone reduces its fanout on
  // rowstream_clk without changing the DDR profile or loader protocol.
  assign pcie_calib_complete_o = TINYSTORIES_LOADER_ONLY ? ddr_ready_q : calib_complete;
  assign pcie_boot_done_o = read_probe_done_q;
  // TinyStories PCIe inference does not consume the wide BIST debug bus.
  // Keep it available for the generic/JTAG diagnostics, but do not let the
  // DDR debug net enter the TinyStories PCIe status cone (it is timing
  // critical on rowstream_clk).
  assign pcie_ddr_debug1_o = TINYSTORIES_LOADER_ONLY ? 32'd0 : debug1;
  assign pcie_loader_done_o = pcie_loader_done_sticky_q;
  assign pcie_loader_error_o = pcie_loader_error_sticky_q;
  assign pcie_loader_last_accepted_o = pcie_loader_last_accepted_sticky_q;
  assign pcie_loader_last_magic_ok_o = pcie_loader_last_magic_ok_sticky_q;
  assign pcie_loader_last_opcode_o = loader_last_opcode_q;
  assign pcie_loader_last_chunk_o = loader_last_chunk_q;
  assign pcie_loader_command_payload_addr_o = loader_command_payload_addr_q;
  assign pcie_loader_wait_cycles_o = loader_wait_cycles_q;
  assign pcie_loader_read_data_o = {{(512 - WB_DATA_BITS){1'b0}}, loader_read_data_q};
  assign pcie_top1_busy_o = top1_reader_busy || top1_cutout_busy;
  assign pcie_top1_done_o = top1_done_sticky_q;
  assign pcie_top1_error_o = top1_error_sticky_q;
  assign pcie_top1_token_o = top1_token_q;
  assign pcie_top1_score_q024_o = top1_score_q024_q;
  assign pcie_top1_rows_scanned_o = top1_rows_scanned_q;
  assign pcie_top1_cycle_count_o = top1_cycle_count_q;
  assign pcie_top1_debug_status_o = {
    9'd0,
    top1_row0_sidecar_decode_mismatch_q,
    top1_row_last,
    top1_row_ready,
    top1_row_valid,
    top1_cutout_error_reserved_bits,
    top1_cutout_busy,
    top1_cutout_done,
    top1_cutout_valid,
    wb_err && top1_reader_wb_cyc,
    wb_ack && top1_reader_wb_cyc,
    wb_stall,
    top1_reader_wb_we,
    top1_reader_wb_stb,
    top1_reader_wb_cyc,
    top1_reader_error,
    top1_reader_done,
    top1_reader_busy,
    top1_start_rejected,
    top1_start_accepted,
    read_probe_done_q,
    calib_complete,
    ddr_ready_q,
    rst_n
  };
  assign pcie_top1_debug_reader_addr_o = {{(32 - WB_ADDR_BITS){1'b0}}, top1_fault_reader_addr_q};
  assign pcie_top1_debug_wb_ack_count_o = {15'd0, top1_fault_seen_q, top1_fault_token_q};
  assign pcie_top1_debug_wb_err_count_o = top1_fault_sidecar_q;
  assign pcie_top1_debug_packet_wb_write_ack_count_o = wb_packet_write_ack_count_q;
  assign pcie_top1_debug_packet_wb_read_ack_count_o = wb_packet_read_ack_count_q;
`endif
endmodule

module task6_uberddr3_loader_jtag_command_shift #(
  parameter int WIDTH = 16,
  parameter int JTAG_CHAIN = 2
) (
  input  logic        controller_clk_i,
  input  logic        rst_ni,
  output logic [WIDTH - 1:0] payload_o,
  output logic        event_o,
  output logic [15:0] command_count_o
);
  logic capture;
  logic drck;
  logic reset;
  logic runtest;
  logic sel;
  logic shift;
  logic tck;
  logic tdi;
  logic tms;
  logic update;
  logic tdo;
  logic [WIDTH - 1:0] shift_q;
  logic [WIDTH - 1:0] payload_tck_q;
  logic [WIDTH - 1:0] payload_meta_q;
  logic [WIDTH - 1:0] payload_sync_q;
  logic toggle_tck_q;
  logic toggle_meta_q;
  logic toggle_sync_q;
  logic toggle_seen_q;

  assign tdo = shift_q[0];

  always_ff @(posedge drck or posedge reset) begin
    if (reset) begin
      shift_q <= '0;
    end else begin
      if (sel && capture)
        shift_q <= payload_tck_q;
      else if (sel && shift)
        shift_q <= {tdi, shift_q[WIDTH - 1:1]};
    end
  end

  always_ff @(posedge tck or posedge reset) begin
    if (reset) begin
      payload_tck_q <= '0;
      toggle_tck_q <= 1'b0;
    end else if (sel && update) begin
        payload_tck_q <= shift_q;
        toggle_tck_q <= ~toggle_tck_q;
    end
  end

  always_ff @(posedge controller_clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      toggle_meta_q <= 1'b0;
      toggle_sync_q <= 1'b0;
      toggle_seen_q <= 1'b0;
      payload_meta_q <= '0;
      payload_sync_q <= '0;
      payload_o <= '0;
      event_o <= 1'b0;
      command_count_o <= 16'd0;
    end else begin
      payload_meta_q <= payload_tck_q;
      payload_sync_q <= payload_meta_q;
      toggle_meta_q <= toggle_tck_q;
      toggle_sync_q <= toggle_meta_q;
      event_o <= toggle_sync_q ^ toggle_seen_q;
      if (toggle_sync_q ^ toggle_seen_q) begin
        toggle_seen_q <= toggle_sync_q;
        payload_o <= payload_sync_q;
        command_count_o <= command_count_o + 16'd1;
      end
    end
  end

  BSCANE2 #(
    .DISABLE_JTAG("FALSE"),
    .JTAG_CHAIN(JTAG_CHAIN)
  ) bscan (
    .CAPTURE(capture),
    .DRCK(drck),
    .RESET(reset),
    .RUNTEST(runtest),
    .SEL(sel),
    .SHIFT(shift),
    .TCK(tck),
    .TDI(tdi),
    .TMS(tms),
    .UPDATE(update),
    .TDO(tdo)
  );
endmodule

module task6_uberddr3_jtag_debug_shift #(
  parameter int WIDTH = 512,
  parameter int JTAG_CHAIN = 1,
  parameter bit DISABLE_JTAG = 0
) (
  input logic [WIDTH - 1:0] payload_i
);
  logic capture;
  logic drck;
  logic reset;
  logic runtest;
  logic sel;
  logic shift;
  logic tck;
  logic tdi;
  logic tms;
  logic update;
  logic tdo;
  logic [WIDTH - 1:0] shift_q;

  assign tdo = shift_q[0];

  always_ff @(posedge drck or posedge reset) begin
    if (reset)
      shift_q <= '0;
    else if (sel && capture)
      shift_q <= payload_i;
    else if (sel && shift)
      shift_q <= {tdi, shift_q[WIDTH - 1:1]};
  end

  generate
    if (DISABLE_JTAG) begin : g_jtag_debug_shift_disabled
      BSCANE2 #(
        .DISABLE_JTAG("TRUE"),
        .JTAG_CHAIN(JTAG_CHAIN)
      ) bscan (
        .CAPTURE(capture),
        .DRCK(drck),
        .RESET(reset),
        .RUNTEST(runtest),
        .SEL(sel),
        .SHIFT(shift),
        .TCK(tck),
        .TDI(tdi),
        .TMS(tms),
        .UPDATE(update),
        .TDO(tdo)
      );
    end else begin : g_jtag_debug_shift_enabled
      BSCANE2 #(
        .DISABLE_JTAG("FALSE"),
        .JTAG_CHAIN(JTAG_CHAIN)
      ) bscan (
        .CAPTURE(capture),
        .DRCK(drck),
        .RESET(reset),
        .RUNTEST(runtest),
        .SEL(sel),
        .SHIFT(shift),
        .TCK(tck),
        .TDI(tdi),
        .TMS(tms),
        .UPDATE(update),
        .TDO(tdo)
      );
    end
  endgenerate
endmodule

`default_nettype wire
