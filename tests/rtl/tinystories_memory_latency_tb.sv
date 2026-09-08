module tb;
  reg clk=0, reset=1, go=0;
  wire done;
  wire [63:0] result;
  always #5 clk=~clk;
  main dut(.clk(clk),.reset(reset),.go(go),.done(done),.result(result));
  initial begin
    dut.memory.mem[0]=64'sd17646;
    dut.memory.mem[1]=-64'sd14372;
    dut.memory.mem[2]=-64'sd9842;
    dut.memory.mem[3]=64'sd2325;
    repeat(3) @(negedge clk);
    reset=0; go=1;
    wait(done); @(negedge clk);
    $display("sum=%0d", $signed(result));
    if (result !== -64'sd4243) $fatal(1,"stale memory read: expected -4243");
    $display("PASS"); $finish;
  end
  initial begin #10000; $fatal(1,"timeout"); end
endmodule
