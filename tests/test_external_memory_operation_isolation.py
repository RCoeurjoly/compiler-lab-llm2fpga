"""A completed join operand must not leave another read for the next phase."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory as em


SOURCE = r'''module main(input logic clk, reset, active,
  input logic [3:0] address, output logic operation_done_in,
  output logic [7:0] a_data, b_data);
  wire operation_go_out = active && !operation_done_in;
  wire a_done, b_done;
  assign operation_done_in = a_done & b_done;
  seq_mem_d1 #(.WIDTH(8), .SIZE(16), .IDX_SIZE(4)) a (
    .clk(clk), .reset(reset), .addr0(address), .content_en(operation_go_out),
    .write_en(1'b0), .write_data(8'd0), .read_data(a_data), .done(a_done));
  seq_mem_d1 #(.WIDTH(8), .SIZE(16), .IDX_SIZE(4)) b (
    .clk(clk), .reset(reset), .addr0(address), .content_en(operation_go_out),
    .write_en(1'b0), .write_data(8'd0), .read_data(b_data), .done(b_done));
endmodule
'''

TB = r'''module tb;
  logic clk=0; always #5 clk=~clk;
  logic reset=1, active=0;
  logic [3:0] address=0;
  wire operation_done_in;
  wire [7:0] a_data, b_data;
  wire [1:0] ext_mem_req_valid;
  logic [1:0] ext_mem_req_ready=0, ext_mem_rsp_valid=0;
  wire [63:0] ext_mem_req_addr;
  logic [127:0] ext_mem_rsp_data=0;
  main dut (.*);
  task tick; @(posedge clk); #1; endtask
  task phase(input logic [3:0] index, input logic [7:0] a, b);
    @(negedge clk); active=1; address=index;
    tick();
    if (ext_mem_req_valid != 2'b11 || ext_mem_req_addr != {28'd0,index,28'd0,index})
      $fatal(1,"fresh phase requests missing or stale");
    // Hold both valid payloads under real request backpressure.
    repeat(3) begin
      tick();
      if(ext_mem_req_valid != 2'b11) $fatal(1,"queued request lost");
    end
    @(negedge clk); ext_mem_req_ready=3;
    tick(); @(negedge clk); ext_mem_req_ready=0;
    ext_mem_rsp_valid=1;
    ext_mem_rsp_data[63:0]=({56'd0,a} << (index[2:0]*8));
    tick(); @(negedge clk); ext_mem_rsp_valid=0;
    // A has completed, but the joined phase must keep waiting for B.
    repeat(8) begin
      tick();
      if(ext_mem_req_valid != 0)
        $fatal(1,"completed join operand reissued before phase ended");
      if(operation_done_in) $fatal(1,"join completed before B responded");
    end
    @(negedge clk); ext_mem_rsp_valid=2;
    ext_mem_rsp_data[127:64]=({56'd0,b} << (index[2:0]*8));
    tick(); @(negedge clk); ext_mem_rsp_valid=0;
    tick();
    if(!operation_done_in || a_data!=a || b_data!=b)
      $fatal(1,"join consumed stale data");
    @(negedge clk); active=0;
    repeat(3) tick();
    if(operation_done_in || ext_mem_req_valid) $fatal(1,"phase did not drain");
  endtask
  initial begin
    repeat(2) tick(); @(negedge clk); reset=0;
    phase(3,8'h11,8'h22);
    phase(4,8'h33,8'h44);
    // Same address, new operation: it must get a fresh response, not cache it.
    phase(4,8'h55,8'h66);
    @(negedge clk); reset=1; tick();
    @(negedge clk); reset=0;
    phase(3,8'h77,8'h88);
    $display("PASS: joined reads issue once per phase and rearm even at the same address");
    $finish;
  end
  initial begin #10000; $fatal(1,"operation isolation timeout"); end
endmodule
'''


class ExternalMemoryOperationIsolationTest(unittest.TestCase):
    def test_completed_operand_does_not_reissue_into_next_join_phase(self):
        self.assertIsNotNone(shutil.which("iverilog"))
        lowered = em.externalize_memories(SOURCE, ["a", "b"]).source
        with tempfile.TemporaryDirectory(prefix="joined-memory-phase-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(lowered + "\n" + TB)
            build = subprocess.run(
                ["iverilog", "-g2012", "-s", "tb", "-o", "sim", "tb.sv"],
                cwd=path, capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run(["vvp", "sim"], cwd=path,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
