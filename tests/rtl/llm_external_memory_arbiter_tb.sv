module llm_external_memory_arbiter_tb;
  logic clk = 0;
  always #5 clk = ~clk;
  logic rst = 1;
  logic [239:0] req_valid = 0;
  logic [239:0] req_ready;
  logic [240*32-1:0] req_addr = '0;
  logic [239:0] rsp_valid;
  logic [240*64-1:0] rsp_data;
  logic wb_cyc, wb_stb, wb_accept = 0, wb_ack = 0, wb_err = 0;
  logic [31:0] wb_addr;
  logic [15:0] wb_sel;
  logic [127:0] wb_rdata = 0;

  llm_external_memory_arbiter #(.PORTS(240)) dut (.*);

  task await_grant;
    while (!(|req_ready)) begin @(posedge clk); #1; end
  endtask
  initial begin #10000; $fatal(1, "arbiter handshake timed out"); end

  initial begin
    repeat (2) @(posedge clk);
    rst <= 0;
    @(negedge clk);
    // Exercise the actual full-model port count and simultaneous requests.
    // The initial cursor starts before port 3. Subsequent grants rotate across
    // active groups, then continue from the previous local port within a group.
    req_addr[3*32 +: 32] = 32'h2b;
    req_addr[12*32 +: 32] = 32'h35;
    req_addr[239*32 +: 32] = 32'h48;
    req_valid[3] = 1'b1;
    req_valid[12] = 1'b1;
    req_valid[239] = 1'b1;
    #1;
    await_grant();
    $display("ready=%b valid=%b state=%0d", req_ready, req_valid, dut.state);
    if (!req_ready[3] || req_ready[12] || req_ready[239] || $countones(req_ready) != 1)
      $fatal(1, "lowest-index one-hot request grant failed");
    @(posedge clk);
    @(negedge clk);
    req_valid[3] = 1'b0;
    if (!wb_cyc || !wb_stb || wb_addr != 32'h2)
      $fatal(1, "wrong wishbone request for port 3");
    wb_accept = 1;
    @(posedge clk);
    @(negedge clk);
    wb_accept = 0;
    wb_rdata = 128'h0123456789abcdef_deadbeefcafef00d;
    wb_ack = 1;
    #1;
    if (|rsp_valid) $fatal(1, "response escaped before registered boundary");
    @(posedge clk);
    #1;
    if (!rsp_valid[3] || rsp_valid[239]) $fatal(1, "wrong first response owner");
    if (rsp_data[3*64 +: 64] != 64'h0123456789abcdef)
      $fatal(1, "wrong upper-line response for port 3");
    @(negedge clk);
    wb_ack = 0;
    #1;
    await_grant();
    if (!req_ready[239] || req_ready[12] || $countones(req_ready) != 1)
      $fatal(1, "pending later-group request was not granted fairly");
    @(posedge clk);
    @(negedge clk);
    req_valid[239] = 1'b0;
    if (!wb_cyc || !wb_stb || wb_addr != 32'h4)
      $fatal(1, "wrong wishbone request for port 239");
    wb_accept = 1;
    @(posedge clk);
    @(negedge clk);
    wb_accept = 0;
    wb_ack = 1;
    #1;
    if (|rsp_valid) $fatal(1, "second response escaped before registered boundary");
    @(posedge clk);
    #1;
    if (!rsp_valid[239] || rsp_valid[3] || rsp_valid[12])
      $fatal(1, "wrong second response owner");
    @(negedge clk);
    wb_ack = 0;
    #1;
    await_grant();
    if (!req_ready[12] || $countones(req_ready) != 1)
      $fatal(1, "pending same-group request was not granted after wraparound");
    @(posedge clk);
    @(negedge clk);
    req_valid[12] = 1'b0;
    if (!wb_cyc || !wb_stb || wb_addr != 32'h3)
      $fatal(1, "wrong wishbone request for port 12");
    wb_accept = 1;
    @(posedge clk);
    @(negedge clk);
    wb_accept = 0;
    wb_ack = 1;
    #1;
    if (|rsp_valid) $fatal(1, "third response escaped before registered boundary");
    @(posedge clk);
    #1;
    if (!rsp_valid[12] || rsp_valid[3] || rsp_valid[239])
      $fatal(1, "wrong third response owner");
    if (rsp_data[12*64 +: 64] != 64'hdeadbeefcafef00d)
      $fatal(1, "wrong lower-line response for port 12");
    @(negedge clk);
    wb_ack = 0;
    $display("PASS");
    $finish;
  end
endmodule
