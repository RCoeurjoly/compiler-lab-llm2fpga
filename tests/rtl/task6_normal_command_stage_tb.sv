`timescale 1ns/1ps
module task6_normal_command_stage_tb;
  reg clk=0;always #5 clk=~clk;
  reg rst_n=0,enabled=1,event_i=0,phase=0,idle=1,ready=1,busy=0,source=0;
  reg [207:0] payload=0;
  wire [207:0] captured;
  wire ev,src,accept,restart;
  wire [19:1] decoded;
  task6_normal_command_stage dut(.clk(clk),.rst_n(rst_n),.enabled(enabled),
    .payload(payload),.event_i(event_i),.accept_phase(phase),.idle(idle),
    .ready(ready),.busy(busy),.source_pcie(source),.payload_q(captured),
    .event_q(ev),.source_pcie_q(src),.accept_q(accept),.restart_q(restart),.decode_q(decoded));
  reg [19:1] want;
  integer op,chunk,flags,magic,checks=0;
  reg wanted_accept,wanted_restart;
  initial begin
    repeat(2) @(negedge clk);rst_n=1;
    for(op=0;op<256;op++) for(chunk=0;chunk<4;chunk++) begin
      @(negedge clk);event_i=1;
      payload={128'hfacecafe_01234567_89abcdef_76543210,32'hc0000013,6'd0,2'(chunk),8'(op),32'h33445244};
      source=op[0];
      // Independent literal classification; invalid opcodes/chunks must not
      // alias a supported command. Pair (0x11) is invalid in the x16 profile.
      want=0;
      case(op)
        3,4,5,6,7,8,9,10,11: want[op]=1;
        1,2,12,13,14,15,16,18,19: if(chunk==0) want[op]=1;
        default: want=0;
      endcase
      @(posedge clk);#1;
      if(captured!==payload || src!==source || !ev || !accept || restart || decoded!==want)
        $fatal(1,"decode/payload/source mismatch opcode=%h chunk=%d",op,chunk);
      checks++;
    end
    for(flags=0;flags<64;flags++) for(magic=0;magic<2;magic++) begin
      @(negedge clk);
      {enabled,event_i,phase,idle,ready,busy}=6'(flags);
      payload[31:0]=magic ? 32'h33445244 : 32'hbad;
      wanted_accept=enabled && event_i && !phase && idle && ready && !busy && magic!=0;
      wanted_restart=enabled && event_i && !phase && idle && !wanted_accept;
      @(posedge clk);#1;
      if(accept!==wanted_accept || restart!==wanted_restart || ev!==(enabled && event_i))
        $fatal(1,"capture qualification mismatch flags=%h magic=%0d",flags,magic);
      checks++;
    end
    @(negedge clk);rst_n=0;#1;
    if(ev || accept || restart || captured || decoded || src) $fatal(1,"reset did not cancel bundle");
    $display("PASS: exhaustive command decode/metadata checks=%0d",checks);$finish;
  end
endmodule
