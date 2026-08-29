// Direct main_1 external-memory diagnostic.  This bypasses the generated
// invoke wrapper and models the one-cycle Calyx memory response contract.
module main1_external_tb;
  logic clk = 0, reset = 0, go = 0;
  wire done;
  always #1 clk = ~clk;

  wire [5:0] a0_addr, a1_addr, a2_addr, a3_addr;
  wire a0_en, a1_en, a2_en, a3_en;
  wire a0_we, a1_we, a2_we, a3_we;
  wire [31:0] a0_wdata, a1_wdata, a2_wdata, a3_wdata;
  logic [31:0] a0_rdata = 0, a1_rdata = 0, a2_rdata = 0, a3_rdata = 0;
  logic a0_done = 0, a1_done = 0, a2_done = 0, a3_done = 0;
  logic [31:0] mem0 [0:63], mem1 [0:63], mem2 [0:63], mem3 [0:63];
  integer i, cycles, mismatches, output_writes, trace_fd;
  logic done_seen = 0;
  always @(posedge done) done_seen = 1;

  main_1 dut(
    .clk(clk), .reset(reset), .go(go), .done(done),
    .arg_mem_0_addr0(a0_addr), .arg_mem_0_content_en(a0_en),
    .arg_mem_0_write_en(a0_we), .arg_mem_0_write_data(a0_wdata),
    .arg_mem_0_read_data(a0_rdata), .arg_mem_0_done(a0_done),
    .arg_mem_1_addr0(a1_addr), .arg_mem_1_content_en(a1_en),
    .arg_mem_1_write_en(a1_we), .arg_mem_1_write_data(a1_wdata),
    .arg_mem_1_read_data(a1_rdata), .arg_mem_1_done(a1_done),
    .arg_mem_2_addr0(a2_addr), .arg_mem_2_content_en(a2_en),
    .arg_mem_2_write_en(a2_we), .arg_mem_2_write_data(a2_wdata),
    .arg_mem_2_read_data(a2_rdata), .arg_mem_2_done(a2_done),
    .arg_mem_3_addr0(a3_addr), .arg_mem_3_content_en(a3_en),
    .arg_mem_3_write_en(a3_we), .arg_mem_3_write_data(a3_wdata),
    .arg_mem_3_read_data(a3_rdata), .arg_mem_3_done(a3_done));

  always_ff @(posedge clk) begin
    if (reset) begin
      a0_done <= 0; a1_done <= 0; a2_done <= 0; a3_done <= 0;
    end else begin
      if (a0_en) $fwrite(trace_fd, "%0d,0,%0d,%0d,%08x\n", cycles, a0_addr, a0_we, a0_wdata);
      if (a1_en) $fwrite(trace_fd, "%0d,1,%0d,%0d,%08x\n", cycles, a1_addr, a1_we, a1_wdata);
      if (a2_en) $fwrite(trace_fd, "%0d,2,%0d,%0d,%08x\n", cycles, a2_addr, a2_we, a2_wdata);
      if (a3_en) $fwrite(trace_fd, "%0d,3,%0d,%0d,%08x\n", cycles, a3_addr, a3_we, a3_wdata);
      a0_done <= a0_en; a1_done <= a1_en; a2_done <= a2_en; a3_done <= a3_en;
      if (a0_en && !a0_we) a0_rdata <= mem0[a0_addr];
      if (a1_en && !a1_we) a1_rdata <= mem1[a1_addr];
      if (a2_en && !a2_we) a2_rdata <= mem2[a2_addr];
      if (a3_en && !a3_we) a3_rdata <= mem3[a3_addr];
      if (a0_en && a0_we) mem0[a0_addr] <= a0_wdata;
      if (a1_en && a1_we) mem1[a1_addr] <= a1_wdata;
      if (a2_en && a2_we) mem2[a2_addr] <= a2_wdata;
      if (a3_en && a3_we) mem3[a3_addr] <= a3_wdata;
      if (a3_en && a3_we) output_writes <= output_writes + 1;
    end
  end

  initial begin
    trace_fd = $fopen("/tmp/lnexec/main1-memory-trace.csv", "w");
    for (i = 0; i < 64; i = i + 1) begin
      mem0[i] = (i[0] ? 32'hffff0000 : 32'h00010000);
      mem1[i] = 32'h00010000;
      mem2[i] = 32'h00000000;
      mem3[i] = 32'h00000000;
    end
    #1 reset = 1;
    output_writes = 0;
    repeat (4) @(posedge clk);
    @(negedge clk); reset = 0; go = 1;
    cycles = 0;
    while (!done_seen && cycles < 200000) begin @(posedge clk); cycles = cycles + 1; end
    @(negedge clk); go = 0;
    mismatches = 0;
    for (i = 0; i < 64; i = i + 1)
      if (mem3[i] !== (i[0] ? 32'hffff0000 : 32'h00010000)) mismatches = mismatches + 1;
    $display("{\"done\":%b,\"done_seen\":%b,\"cycles\":%0d,\"mismatches\":%0d,\"output_writes\":%0d,\"fsm0\":%0d,\"fsm\":%0d}",
      done, done_seen, cycles, mismatches, output_writes, dut.fsm0_out, dut.fsm_out);
    $fclose(trace_fd);
    if (!done_seen || mismatches != 0) $fatal(1);
    $finish;
  end
endmodule
