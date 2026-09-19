`timescale 1ns/1ps
// Both real sequencers and owner muxes; only DDR/clock/JTAG pin boundaries
// are models. The reference is the byte-authenticated pre-overlay shell.
module task6_command_dispatch_tb;
  reg [207:0] payload=0, jtag_payload=0;
  reg event_pcie=0, event_jtag=0;
  wire clk=dut.controller_clk;
  task6_ypcb_uberddr3_bist_rowstream_loader_top #(
    .BYTE_LANES(2), .BIST_MODE_PARAM(2), .BOOT_ISOLATE_UNTIL_CALIB(1),
    .ENABLE_PCIE_TOP1(0), .TINYSTORIES_ENABLE_ENGINE(0), .TINYSTORIES_ENABLE_SERVICE(0)
  ) dut (.clk50(1'b0),.SYS_RSTN(1'b1),.pcie_command_payload_i(payload),
    .pcie_command_event_i(event_pcie),.pcie_status_clear_i(1'b0),
    .pcie_top1_hidden_vector_i(512'd0),.pcie_top1_start_i(1'b0),.pcie_top1_status_clear_i(1'b0),
    .compiler_wb_cyc_i(1'b0),.compiler_wb_stb_i(1'b0),.compiler_wb_we_i(1'b0),
    .compiler_wb_addr_i(25'd0),.compiler_wb_data_i(128'd0),.compiler_wb_sel_i(16'd0));
  reference_loader #(
    .BYTE_LANES(2), .BIST_MODE_PARAM(2), .BOOT_ISOLATE_UNTIL_CALIB(1),
    .ENABLE_PCIE_TOP1(0), .TINYSTORIES_ENABLE_ENGINE(0), .TINYSTORIES_ENABLE_SERVICE(0)
  ) refdut (.clk50(1'b0),.SYS_RSTN(1'b1),.pcie_command_payload_i(payload),
    .pcie_command_event_i(event_pcie),.pcie_status_clear_i(1'b0),
    .pcie_top1_hidden_vector_i(512'd0),.pcie_top1_start_i(1'b0),.pcie_top1_status_clear_i(1'b0),
    .compiler_wb_cyc_i(1'b0),.compiler_wb_stb_i(1'b0),.compiler_wb_we_i(1'b0),
    .compiler_wb_addr_i(25'd0),.compiler_wb_data_i(128'd0),.compiler_wb_sel_i(16'd0));

  // State/output projection compares every rowstream cycle, not just final
  // readback. Free-running absolute timestamp registers are not compared.
  `define STATE(x) {x.read_probe_state_q,x.read_probe_cyc_q,x.read_probe_stb_q, \
    x.read_probe_we_q,x.read_probe_done_q,x.loader_addr_q,x.loader_write_data_q, \
    x.loader_read_data_q,x.loader_sel_q,x.loader_done_q,x.loader_error_q, \
    x.loader_last_accepted_q,x.loader_last_magic_ok_q,x.loader_last_opcode_q, \
    x.loader_last_chunk_q,x.loader_command_payload_addr_q,x.loader_wait_cycles_q, \
    x.loader_packet_data_q[0],x.loader_packet_data_q[1],x.loader_packet_data_q[2], \
    x.loader_packet_data_q[3],x.loader_burst_active_q,x.loader_burst_index_q, \
    x.loader_burst_count_q,x.loader_burst_mismatch_count_q,x.loader_fullbeat_done_q, \
    x.loader_fullbeat_mismatch_count_q,x.read_probe_stream_bytes_q, \
    x.read_probe_stream_valid_q,x.read_probe_stream_mismatch_q, \
    x.loader_read_chunk_q,x.loader_lowbyte_index_q,x.loader_lowbyte_addr_q, \
    x.loader_lowbyte_write_data_q,x.loader_lowbyte_read_data_q, \
    x.loader_lowbyte_read_seen_q,x.loader_lowbyte_write_seen_q, \
    x.loader_dense_write_seen_q,x.loader_dense_write_addr_q,x.loader_dense_write_lane_q, \
    x.loader_dense_write_data_q,x.loader_dense_write_sel_low_q, \
    x.loader_fullbeat_read_after_write_q,x.loader_fullbeat_compare_active_q, \
    x.loader_fullbeat_addr_q,x.loader_fullbeat_expected_base_q,x.loader_fullbeat_write_echo_q, \
    x.loader_packet_write_ack_seen_q,x.loader_packet_read_ack_seen_q, \
    x.loader_packet_write_ack_addr_q,x.loader_packet_write_ack_data_q,x.loader_packet_write_ack_sel_q, \
    x.loader_packet_read_ack_addr_q,x.loader_packet_read_ack_data_q, \
    x.pcie_loader_done_o,x.pcie_loader_error_o,x.pcie_loader_last_accepted_o, \
    x.wb_addr_to_controller,x.wb_data_to_controller,x.wb_sel_to_controller, \
    x.wb_ack,x.wb_err,x.wb_stall}
  wire [2047:0] dut_state=`STATE(dut), ref_state=`STATE(refdut);
  reg [2047:0] ref_previous;
  bit compare_on=0;
  integer comparisons=0, command_count=0;
  always @(posedge clk) begin
    #1;
    if(compare_on) begin
      if(dut_state !== ref_previous)
        $fatal(1,"cycle reference mismatch command=%0d opcode=%h dut_state=%0d ref_state=%0d",
          command_count,payload[39:32],dut.read_probe_state_q,refdut.read_probe_state_q);
      comparisons++;
    end
    ref_previous=ref_state;
  end
  task tick; @(posedge clk);#2;endtask
  task quiet;
    repeat(4) tick();
    while(!dut.read_probe_done_q || !refdut.read_probe_done_q) tick();
    repeat(4) tick();
  endtask
  task send(input [7:0] op,input [31:0] addr,input [127:0] data,
            input bit jtag=0,input [1:0] chunk=0,input bit good_magic=1);
    command_count++;
    @(negedge clk);
    payload={data,addr,6'd0,chunk,op,good_magic ? 32'h33445244 : 32'd0};
    jtag_payload=payload;
    event_pcie=!jtag;event_jtag=jtag;
    tick();
    @(negedge clk);event_pcie=0;event_jtag=0;
    tick();
    // The original two-event protocol ignores the second phase, even busy.
    @(negedge clk);event_pcie=!jtag;event_jtag=jtag;
    tick();
    @(negedge clk);event_pcie=0;event_jtag=0;
  endtask
  integer op,i;
  initial begin
    if($bits(`STATE(dut)) > 2048) $fatal(1,"reference projection is truncated");
    force dut.jtag_command_payload_from_shift=jtag_payload;
    force refdut.jtag_command_payload_from_shift=jtag_payload;
    force dut.jtag_command_event_from_shift=event_jtag;
    force refdut.jtag_command_event_from_shift=event_jtag;
    repeat(30) tick();quiet();
    // RED: unmodified shell echoes immediately; required stage does not.
    @(negedge clk);payload={128'h0123456789abcdef,32'd3,8'd0,8'h0c,32'h33445244};event_pcie=1;
    tick();
    if(dut.loader_last_accepted_q || dut.loader_read_data_q == 128'h0123456789abcdef)
      $fatal(1,"normal command must not dispatch on capture edge");
    @(negedge clk);event_pcie=0;
    tick();
    if(!dut.loader_last_accepted_q || dut.loader_read_data_q != 128'h0123456789abcdef)
      $fatal(1,"normal command must dispatch exactly one cycle after capture");
    @(negedge clk);event_pcie=1;tick();@(negedge clk);event_pcie=0;quiet();
    compare_on=1;
    // Initialize packet slots, then all 19 normal opcodes (0x11 is correctly
    // invalid for this two-lane profile). Alternate the shared PCIe/JTAG mux.
    for(i=0;i<4;i++) begin send('h0f,i,128'hfedcba9876543210+i,i[0]);quiet();end
    for(op=1;op<=19;op++) begin
      send(8'(op),op==16 ? 32'h40000000 : 32'd0,
        op==14 ? 128'd2 : 128'hffeeddccbbaa99887766554433221100,op[0]);quiet();
    end
    for(i=0;i<4;i++) begin send('h12,i,0,i[0]);quiet();end
    // Unsupported opcode, invalid chunk, invalid magic/restart, then recovery.
    send('hff,0,0,1);quiet();send(1,0,0,0,1);quiet();
    send('h0c,0,0,1,0,0);quiet();send('h0c,1,128'h55aa);quiet();
    // Consecutive events overwrite the input fields/source on every edge.
    // Accepted phases alternate; simultaneous events must retain PCIe priority.
    for(i=0;i<12;i++) begin
      @(negedge clk);
      payload={128'h1100+128'(i),32'(i),8'd0,8'h0c,32'h33445244};
      jtag_payload={128'h2200+128'(i),32'(i+1),8'd0,8'h0c,32'h33445244};
      event_pcie=(i%4!=2);event_jtag=1;
      tick();
    end
    @(negedge clk);event_pcie=0;event_jtag=0;payload=0;jtag_payload=0;quiet();
    compare_on=0;
    // A busy event is rejected at capture even if done rises before dispatch.
    force dut.read_probe_done_q=0;force refdut.read_probe_done_q=0;
    @(negedge clk);payload={128'hbad,32'd2,8'd0,8'h0c,32'h33445244};event_pcie=1;
    tick();@(negedge clk);event_pcie=0;
    release dut.read_probe_done_q;release refdut.read_probe_done_q;
    force dut.read_probe_done_q=1;force refdut.read_probe_done_q=1;
    tick();
    if(dut.loader_last_accepted_q || dut.loader_read_data_q==128'hbad)
      $fatal(1,"busy capture became accepted after done rose");
    release dut.read_probe_done_q;release refdut.read_probe_done_q;
    @(negedge clk);event_pcie=1;tick();@(negedge clk);event_pcie=0;quiet();
    // Cold reset cancels a captured command before its dispatch edge.
    @(negedge clk);payload={128'hdead,32'd2,8'd0,8'h0c,32'h33445244};event_pcie=1;
    tick();@(negedge clk);event_pcie=0;force dut.rst_n=0;force refdut.rst_n=0;
    repeat(2)tick();release dut.rst_n;release refdut.rst_n;repeat(30)tick();
    if(dut.loader_last_accepted_q || dut.loader_read_data_q==128'hdead)
      $fatal(1,"reset dispatched stale command");
    $display("PASS: normal command dispatch equivalence and capture safety commands=%0d compared_cycles=%0d",command_count,comparisons);
    $finish;
  end
  initial begin #20000000;$fatal(1,"command stage timeout");end
endmodule
