module llm_external_memory_arbiter_fairness_tb;
  localparam int PORTS = 240;
  localparam int FIRST_BANK_PORT = 232;

  logic clk = 0;
  always #5 clk = ~clk;
  logic rst = 1;
  logic [PORTS-1:0] req_valid;
  logic [PORTS-1:0] req_ready;
  logic [PORTS*32-1:0] req_addr;
  logic [PORTS-1:0] rsp_valid;
  logic [PORTS*64-1:0] rsp_data;
  logic wb_cyc, wb_stb, wb_accept, wb_ack = 0, wb_err = 0;
  logic [31:0] wb_addr;
  logic [15:0] wb_sel;
  logic [127:0] wb_rdata = 128'h0123456789abcdef_deadbeefcafef00d;
  logic wb_pending = 0;
  logic [3:0] client_pending = 0;
  logic [3:0] response_seen = 0;

  always_comb begin
    req_valid = '0;
    for (int i = 0; i < 4; i++) begin
      req_valid[FIRST_BANK_PORT+i] = !client_pending[i];
      req_addr[(FIRST_BANK_PORT+i)*32 +: 32] = 32'h003ae388 + i*32'h10000;
    end
  end

  assign wb_accept = wb_cyc && wb_stb;
  llm_external_memory_arbiter #(.PORTS(PORTS)) dut (.*);

  always_ff @(posedge clk) begin
    if (rst) begin
      wb_ack <= 0;
      wb_pending <= 0;
      client_pending <= 0;
      response_seen <= 0;
    end else begin
      wb_ack <= wb_pending;
      wb_pending <= wb_cyc && wb_stb;
      for (int i = 0; i < 4; i++) begin
        if (req_ready[FIRST_BANK_PORT+i])
          client_pending[i] <= 1;
        if (rsp_valid[FIRST_BANK_PORT+i]) begin
          client_pending[i] <= 0;
          response_seen[i] <= 1;
        end
      end
    end
  end

  initial begin
    repeat (2) @(posedge clk);
    rst = 0;
    repeat (128) @(posedge clk);
    if (response_seen != 4'b1111)
      $fatal(1, "persistent DDR scale-bank requests starved: responses=%b", response_seen);
    $display("PASS: all four persistent scale-bank requesters completed");
    $finish;
  end
endmodule
