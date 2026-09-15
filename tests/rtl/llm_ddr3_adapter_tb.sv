`timescale 1ns/1ps
module llm_ddr3_adapter_tb;
  logic clk=0, rst=1, read_valid=0, wb_accept=0, wb_ack=0, wb_err=0;
  logic [31:0] read_address=0, response_address, wb_addr;
  logic response_valid, response_error, wb_cyc, wb_stb, wb_we;
  logic [7:0] response_data;
  logic [15:0] wb_sel;
  logic [127:0] wb_rdata=0;
  always #5 clk = ~clk;
  llm_ddr3_adapter_shell dut (.*);

  task automatic read_byte(input [31:0] address, input [7:0] expected);
    begin
      @(negedge clk); read_address = address; read_valid = 1;
      @(negedge clk); read_valid = 0;
      wait (wb_cyc); @(negedge clk); wb_accept = 1;
      @(negedge clk); wb_accept = 0; wb_rdata = {16{address[7:0]}};
      wait (wb_stb == 0); // request has been accepted
      wb_ack = 1; @(negedge clk); wb_ack = 0;
      wait (response_valid);
      if (response_address !== address || response_data !== expected)
        $fatal(1, "bad response addr=%h data=%h", response_address, response_data);
    end
  endtask

  initial begin
    repeat (2) @(negedge clk); rst = 0;
    read_byte(32'h10, 8'h10);
    read_byte(32'h03, 8'h03);
    $display("LLM_DDR3_ADAPTER_PASS");
    $finish;
  end
endmodule
