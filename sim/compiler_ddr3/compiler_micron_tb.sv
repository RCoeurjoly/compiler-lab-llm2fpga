// Testbench only. The accelerator, adapter, arbiter, owner mux, controller and
// PHY are separate authenticated/pinned implementation inputs.
`timescale 1ps/1ps
module compiler_micron_tb;
  reg clk=1, ddr_clk=1, ddr_clk_90=1, ref_clk=1, reset_n=0;
  always #6000 clk=~clk;
  always #1500 ddr_clk=~ddr_clk;
  initial begin #750; forever #1500 ddr_clk_90=~ddr_clk_90; end
  always #2500 ref_clk=~ref_clk;
  wire calibrated;
  wire reset = !reset_n || !calibrated;
  reg clear=0, prompt_valid=0, start=0, token_ready=0;
  reg [15:0] prompt_token=0;
  wire prompt_ready, token_valid, busy, error;
  wire [15:0] token_id;
  wire [7:0] error_code;
  wire [31:0] request_count, wb_addr;
  wire wb_cyc, wb_stb, wb_we, wb_ack, wb_err, accelerator_stall;
  wire [15:0] wb_sel;
  wire [127:0] wb_rdata;
  wire wb_accept = !accelerator_stall;
  reg host_cyc=0, host_stb=0, host_we=0;
  reg [24:0] host_addr=0;
  reg [127:0] host_write_data=0;
  wire host_stall, host_ack, host_err;
  wire [127:0] host_read_data;
  wire memory_cyc, memory_stb, memory_we, memory_stall, memory_ack, memory_err;
  wire [24:0] memory_addr;
  wire [127:0] memory_write_data, memory_read_data;
  wire [15:0] memory_sel;
  tinystories_1m_ddr3_command_adapter accelerator (.*);
  task6_wishbone_owner_mux #(.ADDR_BITS(25), .DATA_BITS(128), .DIRECT_ACCELERATOR_OWNER(0)) owner_mux (
    .clk(clk), .rst(reset), .accelerator_enable(1'b1),
    .host_cyc(host_cyc), .host_stb(host_stb), .host_we(host_we),
    .host_addr(host_addr), .host_write_data(host_write_data), .host_sel(16'hffff),
    .host_stall(host_stall), .host_ack(host_ack), .host_err(host_err), .host_read_data(host_read_data),
    .accelerator_cyc(wb_cyc), .accelerator_stb(wb_stb), .accelerator_we(wb_we),
    .accelerator_addr(wb_addr[24:0]), .accelerator_write_data(128'd0),
    .accelerator_sel(wb_sel), .accelerator_stall(accelerator_stall),
    .accelerator_ack(wb_ack), .accelerator_err(wb_err), .accelerator_read_data(wb_rdata),
    .memory_cyc(memory_cyc), .memory_stb(memory_stb), .memory_we(memory_we),
    .memory_addr(memory_addr), .memory_write_data(memory_write_data), .memory_sel(memory_sel),
    .memory_stall(memory_stall), .memory_ack(memory_ack), .memory_err(memory_err),
    .memory_read_data(memory_read_data), .owner_active(), .accelerator_owned()
  );
  uberddr3_micron_memory memory_system (
    .controller_clk(clk), .ddr_clk(ddr_clk), .ddr_clk_90(ddr_clk_90), .ref_clk(ref_clk),
    .reset_n(reset_n), .wb_cyc(memory_cyc), .wb_stb(memory_stb), .wb_we(memory_we),
    .wb_addr(memory_addr), .wb_wdata(memory_write_data), .wb_sel(memory_sel),
    .wb_stall(memory_stall), .wb_ack(memory_ack), .wb_err(memory_err),
    .wb_rdata(memory_read_data), .calibrated(calibrated)
  );
  localparam IMAGE_BYTES=4136720, LINES=258545;
  reg [7:0] host_image [0:IMAGE_BYTES-1]; // Host file buffer, never a DUT preload.
  integer image_fd, bytes_read, trace_fd, line_index, byte_index, token_index;
  string image_path;
  reg load_only=0, corrupt_write=0;
  integer phase=0;
  longint unsigned cycles=0, max_cycles=1000000000;
  longint unsigned host_requests=0, host_responses=0, requests=0, responses=0;
  reg [31:0] response_addr;
  reg [127:0] expected;
  reg memory_was_stalled=0;
  reg [169:0] held_memory_request;
  time last_ddr_edge=0;
  always @(posedge ddr_clk) last_ddr_edge=$time;
  always @(posedge clk) begin
    #1;
    if (last_ddr_edge != $time-1) $fatal(1, "FAIL: clock phase alignment");
  end

  task automatic transaction(input integer address, input bit write_enable);
    integer waited;
    begin
      @(negedge clk);
      host_cyc=1; host_stb=1; host_we=write_enable; host_addr=address;
      waited=0;
      @(posedge clk);
      while (host_stall !== 1'b0) begin
        waited=waited+1;
        if (waited>10000) $fatal(1, "FAIL: host acceptance timeout address=%0d", address);
        @(posedge clk);
      end
      @(negedge clk); host_stb=0;
      while (host_ack !== 1'b1) begin
        waited=waited+1;
        if (waited>10000) $fatal(1, "FAIL: host response timeout address=%0d", address);
        @(negedge clk);
      end
      if (host_err !== 1'b0) $fatal(1, "FAIL: host response error");
      if (!write_enable && host_read_data !== expected)
        $fatal(1, "FAIL: load readback line=%0d expected=%032h actual=%032h", address, expected, host_read_data);
      @(posedge clk); @(negedge clk); host_cyc=0;
      @(posedge clk);
    end
  endtask

  initial begin
    if ($value$plusargs("max_cycles=%d", max_cycles)) begin end
    load_only=$test$plusargs("load_only");
    corrupt_write=$test$plusargs("corrupt_write");
    if (!$value$plusargs("MODEL_BIN=%s", image_path)) $fatal(1, "FAIL: missing MODEL_BIN");
    image_fd=$fopen(image_path, "rb");
    if (!image_fd) $fatal(1, "FAIL: model image open");
    bytes_read=$fread(host_image, image_fd);
    if (bytes_read != IMAGE_BYTES || $fgetc(image_fd) != -1) $fatal(1, "FAIL: model image size");
    $fclose(image_fd);
    trace_fd=$fopen("accelerator-memory.trace", "w");
    if (!trace_fd) $fatal(1, "FAIL: trace open");
    repeat (10) @(negedge clk);
    reset_n=1;
    wait (calibrated === 1'b1);
    if (memory_system.controller.ddr3_controller_inst.wrong_read_data !== 0)
      $fatal(1, "FAIL: BIST errors before host load");
    $display("PASS: startup calibration and BIST cycles=%0d", cycles);
    repeat (4) @(negedge clk);
    phase=1;
    for (line_index=0; line_index<LINES; line_index=line_index+1) begin
      for (byte_index=0; byte_index<16; byte_index=byte_index+1)
        host_write_data[8*byte_index +: 8]=host_image[line_index*16+byte_index];
      if (corrupt_write && line_index==17) host_write_data[0]=~host_write_data[0];
      transaction(line_index, 1);
    end
    phase=2;
    for (line_index=0; line_index<LINES; line_index=line_index+1) begin
      for (byte_index=0; byte_index<16; byte_index=byte_index+1)
        expected[8*byte_index +: 8]=host_image[line_index*16+byte_index];
      transaction(line_index, 0);
    end
    if (host_requests != 2*LINES || host_responses != host_requests)
      $fatal(1, "FAIL: host transaction balance");
    $display("PASS: full image readback bytes=%0d", IMAGE_BYTES);
    if (load_only) begin $fclose(trace_fd); $finish; end
    phase=3;
    for (token_index=0; token_index<4; token_index=token_index+1) begin
      @(negedge clk);
      if (!prompt_ready) $fatal(1, "FAIL: prompt not ready");
      case (token_index)
        0: prompt_token=7454;
        1: prompt_token=2402;
        2: prompt_token=257;
        3: prompt_token=640;
      endcase
      prompt_valid=1;
      @(negedge clk); prompt_valid=0;
    end
    if (prompt_ready) $fatal(1, "FAIL: unexpected fifth prompt acceptance");
    @(negedge clk); start=1;
    @(negedge clk); start=0;
    while (token_valid !== 1'b1) @(negedge clk);
    if (token_id !== 16'd11 || requests != responses || requests==0)
      $fatal(1, "FAIL: token or memory balance token=%0d req=%0d rsp=%0d", token_id, requests, responses);
    repeat (5) begin
      @(negedge clk);
      if (!token_valid || token_id !== 16'd11 || !busy) $fatal(1, "FAIL: output backpressure");
    end
    token_ready=1;
    @(negedge clk);
    if (token_valid || busy) $fatal(1, "FAIL: token handshake retirement");
    $display("PASS: compiler Micron first token=11 cycles=%0d requests=%0d responses=%0d", cycles, requests, responses);
    $fclose(trace_fd);
    $finish;
  end

  always @(posedge clk) begin
    cycles <= cycles+1;
    if (cycles%100000==0)
      $display("PROGRESS: cycles=%0d phase=%0d calibration=%b bist_state=%0d bist_write=%0d bist_read=%0d host_requests=%0d accelerator_requests=%0d responses=%0d",
        cycles, phase, calibrated, memory_system.controller.ddr3_controller_inst.state_calibrate,
        memory_system.controller.ddr3_controller_inst.write_test_address_counter,
        memory_system.controller.ddr3_controller_inst.read_test_address_counter,
        host_requests, requests, responses);
    if (cycles>=max_cycles) $fatal(1, "FAIL: integration watchdog phase=%0d host_requests=%0d", phase, host_requests);
    if (reset_n && memory_system.controller.ddr3_controller_inst.wrong_read_data != 0)
      $fatal(1, "FAIL: BIST read mismatch");
    if (!calibrated && (host_stb || start)) $fatal(1, "FAIL: activity before calibration");
    if (reset) memory_was_stalled <= 0;
    else begin
      if (memory_was_stalled && (!memory_cyc || !memory_stb ||
          {memory_we, memory_addr, memory_write_data, memory_sel} !== held_memory_request))
        $fatal(1, "FAIL: memory request changed under backpressure");
      memory_was_stalled <= memory_cyc && memory_stb && memory_stall;
      held_memory_request <= {memory_we, memory_addr, memory_write_data, memory_sel};
      if (error || wb_err || memory_err) $fatal(1, "FAIL: integration error code=%0d", error_code);
      if (host_ack && wb_ack) $fatal(1, "FAIL: response delivered to both owners");
      if (host_cyc && host_stb && !host_stall) host_requests <= host_requests+1;
      if (host_ack) host_responses <= host_responses+1;
      if (wb_cyc && wb_stb && wb_accept) begin
        if (wb_we || wb_sel !== 16'hffff || wb_addr>=LINES || requests!=responses)
          $fatal(1, "FAIL: invalid/overlapping compiler memory request");
        response_addr <= wb_addr;
        $fdisplay(trace_fd, "Q %0d %08h", requests, wb_addr);
        requests <= requests+1;
      end
      if (wb_ack) begin
        if (requests!=responses+1 || (^wb_rdata === 1'bx)) $fatal(1, "FAIL: invalid compiler response");
        $fdisplay(trace_fd, "R %0d %08h %032h", responses, response_addr, wb_rdata);
        responses <= responses+1;
      end
      if (request_count != requests) $fatal(1, "FAIL: adapter request count mismatch");
    end
  end
endmodule
