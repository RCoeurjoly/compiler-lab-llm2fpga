`timescale 1ns/1ps
module compiler_ddr3_trace_replay_top_tb;
  reg pcie_clk=0; always #8 pcie_clk=~pcie_clk;
  reg clk=0; always #6 clk=~clk;
  reg pcie_reset=1, reset=1, pcie_abort=0, calib_complete=1;
  reg [31:0] s_axi_awaddr=0;
  reg s_axi_awvalid=0;
  wire s_axi_awready;
  reg [31:0] s_axi_wdata=0;
  reg [3:0] s_axi_wstrb=0;
  reg s_axi_wvalid=0;
  wire s_axi_wready;
  wire [1:0] s_axi_bresp;
  wire s_axi_bvalid;
  reg s_axi_bready=0;
  reg [31:0] s_axi_araddr=0;
  reg s_axi_arvalid=0;
  wire s_axi_arready;
  wire [31:0] s_axi_rdata;
  wire [1:0] s_axi_rresp;
  wire s_axi_rvalid;
  reg s_axi_rready=0;
  wire [31:0] l_axi_awaddr;
  wire l_axi_awvalid;
  wire l_axi_awready;
  wire [31:0] l_axi_wdata;
  wire [3:0] l_axi_wstrb;
  wire l_axi_wvalid;
  wire l_axi_wready;
  wire [1:0] l_axi_bresp;
  wire l_axi_bvalid;
  wire l_axi_bready;
  wire [31:0] l_axi_araddr;
  wire l_axi_arvalid;
  wire l_axi_arready;
  wire [31:0] l_axi_rdata;
  wire [1:0] l_axi_rresp;
  wire l_axi_rvalid;
  wire l_axi_rready;
  wire wb_cyc, wb_stb, wb_we, wb_stall, wb_ack, wb_err;
  wire [24:0] wb_addr; wire [15:0] wb_sel; wire [127:0] wb_rdata;
  compiler_ddr3_trace_replay_bridge dut(.*);
  reg host_cyc=0,host_stb=0,host_we=0; reg [24:0] host_addr=0;
  reg [127:0] host_wdata=0; wire [127:0] host_rdata;
  wire host_ack,host_err,host_stall;
  task6_pcie_axil_rowstream_loader_ingress #(.COMMAND_WIDTH(208),.COMMAND_DATA_LSB(80)) loader(
    .clk(pcie_clk),
    .rst_n(!pcie_reset),
    .calib_complete_i(1'b1),
    .boot_done_i(1'b1),
    .ddr_debug1_i('0),
    .debug_rowstream_heartbeat_count_i('0),
    .debug_rowstream_status_i('0),
    .debug_rowstream_seen_i('0),
    .loader_done_i(1'b0),
    .loader_error_i(1'b0),
    .loader_last_accepted_i(1'b0),
    .loader_last_magic_ok_i(1'b0),
    .loader_last_opcode_i('0),
    .loader_last_chunk_i('0),
    .loader_command_payload_addr_i('0),
    .loader_wait_cycles_i('0),
    .loader_read_data_i({384'd0,host_rdata}),
    .top1_busy_i(1'b0),
    .top1_done_i(1'b0),
    .top1_error_i(1'b0),
    .top1_token_i('0),
    .top1_score_q024_i('0),
    .top1_rows_scanned_i('0),
    .top1_cycle_count_i('0),
    .top1_debug_status_i('0),
    .top1_debug_reader_addr_i('0),
    .top1_debug_wb_ack_count_i('0),
    .top1_debug_wb_err_count_i('0),
    .top1_debug_packet_wb_write_ack_count_i('0),
    .top1_debug_packet_wb_read_ack_count_i('0),
    .mlp_selftest_present_i(1'b0),
    .mlp_selftest_status_i('0),
    .mlp_selftest_cycle_count_i('0),
    .mlp_selftest_fail_detail_i('0),
    .mlp_selftest_fail_values_i('0),
    .mlp_selftest_first_add_sample_i('0),
    .mlp_selftest_first_requant_sample_i('0),
    .mlp_selftest_requant_debug0_i('0),
    .mlp_selftest_requant_debug1_i('0),
    .mlp_accel_status_i('0),
    .mlp_accel_cycle_count_i('0),
    .mlp_accel_output_checksum_i('0),
    .mlp_accel_output_sample0_i('0),
    .mlp_accel_output_sample1_i('0),
    .mlp_accel_output_vector_i('0),
    .m2_full_block_status_i('0),
    .m2_full_block_cycle_count_i('0),
    .m2_full_block_output_checksum_i('0),
    .m2_full_block_output_sample0_i('0),
    .m2_full_block_output_sample1_i('0),
    .m2_full_block_output_count_i('0),
    .m2_full_block_debug_i('0),
    .m2_full_block_debug1_i('0),
    .m2_full_block_debug2_i('0),
    .m2_full_block_debug3_i('0),
    .m2_full_block_provenance_i('0),
    .m2_full_block_output_hash_i('0),
    .m2_full_block_output_vector_i('0),
    .tinystories_prompt_ready_i(1'b0),
    .tinystories_busy_i(1'b0),
    .tinystories_error_i(1'b0),
    .tinystories_error_code_i('0),
    .tinystories_debug_i('0),
    .tinystories_bridge_error_i(1'b0),
    .tinystories_requests_i('0),
    .tinystories_cache_hits_i('0),
    .tinystories_cache_misses_i('0),
    .tinystories_stall_cycles_i('0),
    .tinystories_token_count_i('0),
    .tinystories_token_overflow_i(1'b0),.s_axi_awaddr(l_axi_awaddr),
    .s_axi_awvalid(l_axi_awvalid),
    .s_axi_awready(l_axi_awready),
    .s_axi_wdata(l_axi_wdata),
    .s_axi_wstrb(l_axi_wstrb),
    .s_axi_wvalid(l_axi_wvalid),
    .s_axi_wready(l_axi_wready),
    .s_axi_bresp(l_axi_bresp),
    .s_axi_bvalid(l_axi_bvalid),
    .s_axi_bready(l_axi_bready),
    .s_axi_araddr(l_axi_araddr),
    .s_axi_arvalid(l_axi_arvalid),
    .s_axi_arready(l_axi_arready),
    .s_axi_rdata(l_axi_rdata),
    .s_axi_rresp(l_axi_rresp),
    .s_axi_rvalid(l_axi_rvalid),
    .s_axi_rready(l_axi_rready)
  );
  wire mc,ms,mw;wire [24:0] ma;wire [127:0] md;wire [15:0] sel;
  reg stall=0, ack=0;reg [127:0] data=0;
  task6_wishbone_owner_mux #(.ADDR_BITS(25),.DATA_BITS(128)) owner(
    .clk(clk),.rst(reset),.accelerator_enable(1'b1),
    .host_cyc(host_cyc),.host_stb(host_stb),.host_we(host_we),.host_addr(host_addr),
    .host_write_data(host_wdata),.host_sel(16'hffff),.host_stall(host_stall),
    .host_ack(host_ack),.host_err(host_err),.host_read_data(host_rdata),
    .accelerator_cyc(wb_cyc),.accelerator_stb(wb_stb),.accelerator_we(wb_we),
    .accelerator_addr(wb_addr),.accelerator_write_data(128'd0),.accelerator_sel(wb_sel),
    .accelerator_stall(wb_stall),.accelerator_ack(wb_ack),.accelerator_err(wb_err),
    .accelerator_read_data(wb_rdata),.memory_cyc(mc),.memory_stb(ms),.memory_we(mw),
    .memory_addr(ma),.memory_write_data(md),.memory_sel(sel),.memory_stall(stall),
    .memory_ack(ack),.memory_err(1'b0),.memory_read_data(data),.owner_active(),.accelerator_owned()
  );
  reg [127:0] memory[0:7];
  reg accepted=0,accepted_owner=0,hold_response=0;
  integer delay_count=0, requests=0;
  always @(posedge clk) begin
    if(reset) begin accepted<=0; ack<=0; end
    else begin
      ack<=0;
      if(host_ack && wb_ack) $fatal(1,"both masters received ACK");
      if(accepted && (!mc || owner.select_accelerator!==accepted_owner))
        $fatal(1,"owner changed with request outstanding");
      if(mc && ms && !stall) begin
        if(accepted) $fatal(1,"second physical request outstanding");
        if(ma>7) $fatal(1,"invalid address reached physical memory");
        accepted<=1;accepted_owner<=owner.select_accelerator;delay_count<=4;requests<=requests+1;
        if(mw) memory[ma]<=md;
        data<=memory[ma];
      end
      if(accepted && !hold_response) begin
        if(delay_count==0) begin ack<=1;accepted<=0;end
        else delay_count<=delay_count-1;
      end
    end
  end

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
  task host(input bit write_enable,input [24:0] address,input [127:0] data);
    @(negedge clk);host_cyc=1;host_stb=1;host_we=write_enable;host_addr=address;host_wdata=data;
    do @(posedge clk);while(host_stall);
    @(negedge clk);host_stb=0;
    while(!host_ack) begin @(posedge clk);#1;end
    if(!write_enable && host_rdata!==data) $fatal(1,"full fixture readback");
    @(negedge clk);host_cyc=0;
    repeat(3) @(posedge clk);
  endtask

  integer i,before_count;
  localparam [127:0] BASE=128'hffeeddcc_bbaa9988_77665544_33221100;
  initial begin
    #120; @(negedge pcie_clk);pcie_reset=0;@(negedge clk);reset=0;
    rd(0,32'h54365043);rd('h900,32'h52504c59);rd('h904,1);
    for(i=0;i<8;i=i+1) host(1,i,BASE+i);
    for(i=0;i<8;i=i+1) host(0,i,BASE+i);
    wr('h90c,3);push(2,BASE+2);
    // START while a loader transaction is accepted but not yet acknowledged.
    hold_response=1;
    fork
      begin host(0,4,BASE+4);end
      begin
        wait(accepted);wr('h908,1);repeat(12)tick();
        if(owner.select_accelerator || wb_ack) $fatal(1,"START stole host response");
        @(negedge clk);hold_response=0;
      end
    join
    repeat(80)tick();rd('h928,1);rd('h940,1);
    if(!wb_cyc) $fatal(1,"starvation released replay ownership");
    fork
      begin host(0,3,BASE+3);end
      begin
        repeat(8)tick();if(host_ack) $fatal(1,"host escaped replay ownership");
        stall=1;push(5,BASE+5);repeat(12)tick();
        if(!wb_stb || wb_addr!=5) $fatal(1,"stalled replay request lost");
        @(negedge clk);stall=0;push(2,BASE+2);wr('h908,4);
      end
    join
    repeat(60)tick();rd('h928,2);rd('h940,3);
    wr('h908,2);wr('h90c,1);push(1,0);wr('h908,4);wr('h908,1);
    repeat(60)tick();rd('h928,3);rd('h944,1);
    wr('h908,2);wr('h90c,1);push(1,BASE+1);
    hold_response=1;wr('h908,1);
    wait(accepted);@(negedge pcie_clk);pcie_abort=1;
    repeat(12)tick();@(negedge pcie_clk);pcie_abort=0;
    rd('h928,3);rd('h944,8);
    if(!wb_cyc) $fatal(1,"abort released outstanding response");
    fork
      begin wr('h908,2);end
      begin
        repeat(20)tick();
        if(!dut.pending) $fatal(1,"CLEAR discarded outstanding response");
        @(negedge clk);hold_response=0;
      end
    join
    rd('h928,0);host(0,1,BASE+1);
    // Out-of-range addresses must fail, never alias a valid physical line.
    before_count=requests;wr('h90c,1);push(32'h02000001,BASE+1);wr('h908,4);wr('h908,1);
    repeat(50)tick();rd('h928,3);rd('h944,2);
    if(requests!=before_count) $fatal(1,"address was silently truncated");
    $display("PASS: integrated loader/replay/CDC/drain");$finish;
  end
  initial begin #10000000;$fatal(1,"test timeout");end
endmodule
