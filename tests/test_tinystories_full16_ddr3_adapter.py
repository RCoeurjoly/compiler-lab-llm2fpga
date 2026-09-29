"""Native framing tests, not model/inference substitutes.

The indexed-result fixture replaces only the expensive generated compute core.
The adapter, 86-port arbiter, and registered Wishbone boundary are real RTL.
Wrong result indexing, premature retirement, or ignoring clear must fail.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

TB = r'''
module main(
 input wire clk, reset, start, valid,
 input wire [3:0] token_index,
 input wire [15:0] prompt_0, prompt_1, prompt_2, prompt_3,
 output reg done=0, output wire [15:0] token_id,
 output wire [85:0] ext_mem_req_valid,
 input wire [85:0] ext_mem_req_ready,
 output wire [2751:0] ext_mem_req_addr,
 input wire [85:0] ext_mem_rsp_valid,
 input wire [5503:0] ext_mem_rsp_data
);
 reg [3:0] age=0;
 reg completed=0;
 // Distinct high-bit results catch truncation and misordered indexes.
 assign token_id = 16'hb400 + token_index;
 assign ext_mem_req_valid = '0;
 assign ext_mem_req_addr = '0;
 always @(posedge clk) begin
  if (reset) begin age<=0; done<=0; completed<=0; end
  else if (!start) begin age<=0; done<=0; completed<=0; end
  else begin
   done<=0;
   if (start) begin
    if (!valid || prompt_0!=7454 || prompt_1!=2402 || prompt_2!=257 || prompt_3!=640)
     $fatal(1,"changed prompt/run contract");
    if (completed && !done) $fatal(1,"restarted completed core while draining outputs");
    if (!completed && age==7) begin completed<=1; done<=1; end
    else age<=age+1;
   end
  end
 end
endmodule

module tb;
 reg clk=0; always #5 clk=~clk;
 reg reset=1, clear=0, prompt_valid=0, start=0, token_ready=0;
 reg [15:0] prompt_token=0;
 wire prompt_ready, token_valid, busy, error;
 wire [15:0] token_id;
 wire [7:0] error_code;
 wire [31:0] request_count, wb_addr;
 wire [15:0] wb_sel;
 wire wb_cyc, wb_stb, wb_we;
 reg wb_accept=0, wb_ack=0, wb_err=0;
 reg [127:0] wb_rdata=0;
 tinystories_1m_ddr3_command_adapter #(
  .MEMORY_PORTS(86), .TOKEN_INDEX_WIDTH(4), .RESULT_COUNT(16)
 ) dut(.*);
 task tick; @(posedge clk); #1; endtask
 task send(input [15:0] word);
  @(negedge clk); prompt_valid=1; prompt_token=word;
  if (!prompt_ready) $fatal(1,"prompt unavailable");
  tick(); @(negedge clk); prompt_valid=0;
 endtask
 task launch;
  send(7454); send(2402); send(257); send(640);
  @(negedge clk); start=1; tick(); @(negedge clk); start=0;
 endtask
 integer n, waits;
 initial begin
  repeat(2) tick(); @(negedge clk); reset=0;
  launch();
  // CLEAR must reset the compute/control boundary, not merely the adapter.
  repeat(3) tick(); @(negedge clk); clear=1; tick();
  @(negedge clk); clear=0;
  if (busy || token_valid || !prompt_ready) $fatal(1,"clear did not cancel run");
  launch();
  waits=0;
  while (!token_valid && waits<30) begin tick(); waits=waits+1; end
  if (!token_valid) $fatal(1,"completion produced no result");
  for (n=0;n<16;n=n+1) begin
   waits=0;
   while (!token_valid && waits<5) begin tick(); waits=waits+1; end
   if (!token_valid || token_id!==16'hb400+n)
    $fatal(1,"missing, truncated, or misordered result slot %0d: %h",n,token_id);
   // A duplicate START during output must not restart or skip a slot.
   @(negedge clk); start=1;
   repeat(3) begin
    tick();
    if (!busy || !token_valid || token_id!==16'hb400+n || prompt_ready)
     $fatal(1,"result changed under backpressure at %0d",n);
   end
   @(negedge clk); start=0; token_ready=1;
   tick(); @(negedge clk); token_ready=0;
  end
  repeat(4) tick();
  if (busy || token_valid || error || request_count || wb_stb)
   $fatal(1,"last result not retired exactly once");
  // Reusing the stored prompt without CLEAR must also restart at slot zero.
  @(negedge clk); start=1; tick(); @(negedge clk); start=0; waits=0;
  while (!token_valid && waits<30) begin tick(); waits=waits+1; end
  if (!token_valid || token_id!==16'hb400) $fatal(1,"restart retained previous result index");
  // Clear while draining and reload the prompt for another invocation.
  @(negedge clk); clear=1; tick(); @(negedge clk); clear=0;
  launch(); waits=0;
  while (!token_valid && waits<30) begin tick(); waits=waits+1; end
  if (!token_valid || token_id!==16'hb400) $fatal(1,"clear failed to rearm index zero");
  @(negedge clk); reset=1; tick(); @(negedge clk); reset=0;
  if (busy || token_valid || !prompt_ready) $fatal(1,"reset failed while draining");
  $display("PASS: sixteen indexed results, stalls, clear, reset, duplicate START");
  $finish;
 end
 initial begin #10000; $fatal(1,"framing timed out"); end
endmodule
'''


class Full16Ddr3AdapterTest(unittest.TestCase):
    def test_sixteen_indexed_results_and_run_lifecycle(self):
        self.run_native(TB)

    def test_sixteen_results_cross_actual_pcie_token_cdc(self):
        self.run_native(TB.split("module tb;")[0] + r'''
module tb;
 reg clk=0; always #5 clk=~clk;
 reg pcie_clk=0; always #8 pcie_clk=~pcie_clk;
 reg reset=1, clear=0, prompt_valid=0, start=0;
 reg pcie_rst_n=0, pcie_start=0;
 reg [15:0] prompt_token=0;
 wire prompt_ready, token_valid, token_ready, busy, error;
 wire [15:0] token_id;
 wire [7:0] error_code;
 wire [31:0] request_count, wb_addr;
 wire [15:0] wb_sel;
 wire wb_cyc, wb_stb, wb_we;
 wire wb_accept=0, wb_ack=0, wb_err=0;
 wire [127:0] wb_rdata=0;
 wire [5:0] pcie_token_count;
 wire [511:0] pcie_tokens;
 wire pcie_overflow;
 tinystories_1m_ddr3_command_adapter #(
  .MEMORY_PORTS(86), .TOKEN_INDEX_WIDTH(4), .RESULT_COUNT(16)
 ) dut(.*);
 task6_tinystories_token_cdc cdc(
  .rowstream_clk(clk), .rowstream_rst_n(!reset),
  .pcie_clk(pcie_clk), .pcie_rst_n(pcie_rst_n),
  .pcie_start(pcie_start), .pcie_clear(1'b0),
  .rowstream_token_valid(token_valid), .rowstream_token_ready(token_ready),
  .rowstream_token_id(token_id), .pcie_token_count(pcie_token_count),
  .pcie_tokens(pcie_tokens), .pcie_overflow(pcie_overflow));
 task send(input [15:0] word);
  @(negedge clk); prompt_valid=1; prompt_token=word;
  if(!prompt_ready) $fatal(1,"prompt unavailable");
  @(negedge clk); prompt_valid=0;
 endtask
 integer n;
 initial begin
  repeat(4) @(negedge pcie_clk); pcie_rst_n=1;
  @(negedge clk); reset=0;
  @(negedge pcie_clk); pcie_start=1;
  @(negedge pcie_clk); pcie_start=0;
  send(7454); send(2402); send(257); send(640);
  @(negedge clk); start=1; @(negedge clk); start=0;
  wait(pcie_token_count==16);
  for(n=0;n<16;n=n+1)
   if(pcie_tokens[n*16+:16] !== 16'hb400+n)
    $fatal(1,"PCIe collector lost/reordered slot %0d",n);
  repeat(20) @(negedge pcie_clk);
  if(pcie_token_count!=16 || pcie_overflow || busy || token_valid)
   $fatal(1,"PCIe collector duplicated/dropped final token");
  $display("PASS: sixteen indexed results through actual asynchronous PCIe token CDC");
  $finish;
 end
 initial begin #10000; $fatal(1,"PCIe CDC framing timed out"); end
endmodule
''', include_cdc=True)

    def run_native(self, testbench, *, include_cdc=False):
        self.assertIsNotNone(shutil.which("iverilog"))
        with tempfile.TemporaryDirectory(prefix="full16-command-framing-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(testbench)
            sources = [
                "iverilog", "-g2012", "-s", "tb", "-o", "test.vvp", "tb.sv",
                str(ROOT / "rtl/tinystories_1m_ddr3_command_adapter.sv"),
                str(ROOT / "rtl/tinystories_1m_ddr3_backend.sv"),
                str(ROOT / "rtl/memory/llm_external_memory_arbiter.sv"),
                str(ROOT / "rtl/memory/llm_wishbone_pipeline.sv"),
            ]
            if include_cdc:
                for name in ("task6_tinystories_token_cdc.sv", "task6_tinystories_token_collector.sv"):
                    sources.append(str(ROOT / "third_party/task6-e368449/fpga/rtl" / name))
            build = subprocess.run(sources, cwd=path, capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            # Width/unknown-parameter warnings are integration failures, not
            # harmless elaboration success from silent pruning/padding.
            unexpected = [line for line in build.stderr.splitlines()
                          if not line.endswith("sorry: constant selects in always_* processes are not currently supported (all bits will be included).")]
            self.assertEqual(unexpected, [], build.stderr)
            run = subprocess.run(["vvp", "test.vvp"], cwd=path,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: sixteen indexed results", run.stdout)
