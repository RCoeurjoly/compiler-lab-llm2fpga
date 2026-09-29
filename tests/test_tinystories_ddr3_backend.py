"""Exercise the real backend; the compute fixture is not an inference oracle."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

TB = r'''
module main (
 input wire clk, reset, start, valid,
 input wire [`INDEX_BITS-1:0] token_index,
 input wire [15:0] prompt_0, prompt_1, prompt_2, prompt_3,
 output reg done=0, output wire [15:0] token_id,
 output wire [`PORTS-1:0] ext_mem_req_valid,
 input wire [`PORTS-1:0] ext_mem_req_ready,
 output wire [`PORTS*32-1:0] ext_mem_req_addr,
 input wire [`PORTS-1:0] ext_mem_rsp_valid,
 input wire [`PORTS*64-1:0] ext_mem_rsp_data
);
 reg issued=0;
 assign token_id = 16'hc300 + 16'(token_index);
 assign ext_mem_req_valid = (start && !issued) ? (`PORTS'(1) << (`PORTS-1)) : '0;
 assign ext_mem_req_addr = (`PORTS*32)'(112) << ((`PORTS-1)*32);
 always @(posedge clk) begin
  if (reset) begin issued<=0; done<=0; end
  else begin
   if (start && !valid) $fatal(1,"lost valid");
   if (ext_mem_req_ready[`PORTS-1] && ext_mem_req_valid[`PORTS-1]) issued<=1;
   if (|ext_mem_rsp_valid) begin
    if (ext_mem_rsp_valid !== (`PORTS'(1) << (`PORTS-1)) ||
        ext_mem_rsp_data[(`PORTS-1)*64+:64] !== 64'ha55a1234cafef00d)
     $fatal(1,"response delivered to wrong bank/word");
    done<=1;
   end
  end
 end
endmodule

module tb;
 reg clk=0; always #5 clk=~clk;
 reg reset=1, start=0, valid=0;
 reg [`INDEX_BITS-1:0] token_index='1;
 reg [15:0] prompt_0=7454, prompt_1=2402, prompt_2=257, prompt_3=640;
 wire done, wb_cyc, wb_stb, wb_we;
 wire [15:0] token_id, wb_sel;
 wire [31:0] wb_addr;
 reg wb_ack=0, wb_err=0;
 reg [127:0] wb_rdata=128'hdeadbeef99887766a55a1234cafef00d;
 reg pending=0;
 integer age=0, accepted=0, clocks=0;
 wire wb_accept = wb_stb && !pending && clocks>8;
 tinystories_1m_ddr3_backend #(
  .MEMORY_PORTS(`PORTS), .TOKEN_INDEX_WIDTH(`INDEX_BITS)
 ) dut(.*);
 always @(posedge clk) begin
  clocks<=clocks+1; wb_ack<=0;
  if(wb_accept) begin
   if (!wb_cyc || wb_we || wb_addr!=7 || wb_sel!=16'hffff)
    $fatal(1,"wrong line address/read-only boundary");
   pending<=1; age<=0; accepted<=accepted+1;
  end
  if(pending) begin
   if(!wb_cyc) $fatal(1,"dropped pending transaction");
   if(age==4) begin pending<=0; wb_ack<=1; end
   else age<=age+1;
  end
 end
 initial begin
  repeat(2) @(negedge clk); reset=0; start=1; valid=1;
  wait(done); @(negedge clk); start=0; valid=0;
  if(accepted!=1 || token_id !== (16'hc300 + ((1<<`INDEX_BITS)-1)))
   $fatal(1,"duplicate request or truncated result index");
  repeat(4) @(negedge clk);
  if(wb_stb || accepted!=1) $fatal(1,"spurious request after completion");
  $display("PASS: last-port read, delayed response and full result index"); $finish;
 end
 initial begin #2000; $fatal(1,"backend timeout"); end
endmodule
'''


class TinyStoriesDdr3BackendContractTest(unittest.TestCase):
    def test_last_port_response_and_result_index_for_both_supported_models(self):
        self.assertIsNotNone(shutil.which("iverilog"))
        for ports, index_bits in ((240, 1), (86, 4)):
            with self.subTest(ports=ports), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / "tb.sv").write_text(TB)
                build = subprocess.run([
                    "iverilog", "-g2012", "-s", "tb", f"-DPORTS={ports}",
                    f"-DINDEX_BITS={index_bits}", "-o", "test.vvp", "tb.sv",
                    str(ROOT / "rtl/tinystories_1m_ddr3_backend.sv"),
                    str(ROOT / "rtl/memory/llm_external_memory_arbiter.sv"),
                    str(ROOT / "rtl/memory/llm_wishbone_pipeline.sv"),
                ], cwd=path, capture_output=True, text=True, timeout=30)
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                unexpected = [line for line in build.stderr.splitlines()
                              if not line.endswith("sorry: constant selects in always_* processes are not currently supported (all bits will be included).")]
                self.assertEqual(unexpected, [], build.stderr)
                run = subprocess.run(["vvp", "test.vvp"], cwd=path,
                                     capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn("PASS: last-port read", run.stdout)
