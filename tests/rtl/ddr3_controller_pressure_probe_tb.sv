`timescale 1ns/1ps
module ddr3_controller_pressure_probe_tb;
  logic clk = 0, rst = 1, start = 0;
  logic done;
  logic [31:0] responses;
  logic wb_cyc, wb_stb, wb_we;
  logic [31:0] wb_addr;
  logic [15:0] wb_sel;
  logic wb_accept = 0, wb_ack = 0, wb_err = 0;
  logic [127:0] wb_rdata = 128'h0123456789abcdef0011223344556677;
  logic pending;
  integer cycles = 0;

  always #5 clk = ~clk;
  ddr3_controller_pressure_probe #(.REQUESTS(8)) dut (
    .clk, .rst, .start, .done, .responses, .wb_cyc, .wb_stb, .wb_we,
    .wb_addr, .wb_sel, .wb_accept, .wb_ack, .wb_err, .wb_rdata
  );

  always @(posedge clk) begin
    wb_accept <= wb_cyc;
    wb_ack <= pending;
    pending <= wb_cyc && wb_accept;
    cycles <= cycles + 1;
    if (cycles > 200) begin
      $display("FAIL timeout responses=%0d", responses);
      $finish(1);
    end
  end

  initial begin
    repeat (3) @(posedge clk);
    rst <= 0;
    @(posedge clk); start <= 1;
    @(posedge clk); start <= 0;
    wait (done);
    if (responses != 8) begin
      $display("FAIL response count=%0d", responses);
      $finish(1);
    end
    $display("PRESSURE_PROBE_PASS responses=%0d cycles=%0d", responses, cycles);
    $finish(0);
  end
endmodule
