`timescale 1ns/1ps
module tb_gptneo_softmax_only;
  reg clk=0, rst=1, start=0, in_valid=0, out_ready=1;
  reg [4:0] position=3; reg signed [31:0] in_score;
  wire in_ready, out_valid, busy; wire [4:0] out_index; wire [20:0] out_probability;
  integer n, failures=0;
  reg [20:0] expected [0:3];
  gptneo_softmax_only #(.TMAX(32), .EXP_FILE("/tmp/kev-attn/gptneo_exp.mem")) dut(.*);
  always #5 clk = ~clk;
  initial begin
    expected[0]=229710; expected[1]=207525; expected[2]=427482; expected[3]=183857;
    repeat (2) @(posedge clk); rst<=0; @(posedge clk); start<=1; @(posedge clk); start<=0;
    for (n=0; n<4; n=n+1) begin
      @(posedge clk); in_valid<=1;
      case(n) 0: in_score<=-31; 1: in_score<=-57; 2: in_score<=128; 3: in_score<=-88; endcase
    end
    @(posedge clk); in_valid<=0;
    wait (out_valid);
    for (n=0; n<4; n=n+1) begin
      @(posedge clk); if (out_probability !== expected[n]) begin $display("mismatch %0d: %0d != %0d", n, out_probability, expected[n]); failures=failures+1; end
    end
    if (failures==0) $display("GPTNEO_SOFTMAX_ONLY_PASS"); else $fatal(1);
    $finish;
  end
endmodule
