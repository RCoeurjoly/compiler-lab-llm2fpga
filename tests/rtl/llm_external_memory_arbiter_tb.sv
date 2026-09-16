module llm_external_memory_arbiter_tb;
  logic clk = 0;
  always #5 clk = ~clk;
  logic rst = 1;
  logic [1:0] req_valid = 0;
  logic [1:0] req_ready;
  logic [63:0] req_addr;
  logic [1:0] rsp_valid;
  logic [127:0] rsp_data;
  logic wb_cyc, wb_stb, wb_accept = 0, wb_ack = 0, wb_err = 0;
  logic [31:0] wb_addr;
  logic [15:0] wb_sel;
  logic [127:0] wb_rdata = 0;

  llm_external_memory_arbiter #(.PORTS(2)) dut (.*);

  initial begin
    repeat (2) @(posedge clk);
    rst <= 0;
    @(negedge clk);
    req_addr[63:32] <= 32'h28;
    req_valid[1] <= 1'b1;
    #1;
    $display("ready=%b valid=%b state=%0d", req_ready, req_valid, dut.state);
    if (!req_ready[1] || req_ready[0]) $fatal(1, "wrong owner ready");
    @(posedge clk);
    @(negedge clk);
    @(negedge clk);
    req_valid <= 0;
    if (!wb_cyc || !wb_stb || wb_addr != 32'h2) $fatal(1, "wrong wishbone request");
    wb_accept <= 1;
    @(negedge clk);
    wb_accept <= 0;
    wb_rdata <= 128'h0123456789abcdef_deadbeefcafef00d;
    wb_ack <= 1;
    #1;
    if (!rsp_valid[1] || rsp_valid[0]) $fatal(1, "wrong response owner");
    if (rsp_data[127:64] != 64'h0123456789abcdef) $fatal(1, "wrong upper-line response");
    @(posedge clk);
    @(negedge clk);
    wb_ack <= 0;
    $display("PASS");
    $finish;
  end
endmodule
