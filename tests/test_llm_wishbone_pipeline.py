import subprocess
import tempfile
import unittest
from pathlib import Path


TB = r'''
module wb_pipeline_tb;
  logic clk = 0; always #5 clk = ~clk;
  logic rst = 1;
  logic m_cyc=0, m_stb=0, m_we=0;
  logic [31:0] m_addr=0; logic [15:0] m_sel=0;
  wire m_accept, m_ack, m_err; wire [127:0] m_rdata;
  wire s_cyc, s_stb, s_we; wire [31:0] s_addr; wire [15:0] s_sel;
  logic s_accept=0, s_ack=0, s_err=0; logic [127:0] s_rdata=0;
  llm_wishbone_pipeline dut (.*);
  task tick; @(posedge clk); #1; endtask
  initial begin
    repeat (2) tick(); rst=0;
    @(negedge clk); m_cyc=1; m_stb=1; m_addr=32'h123; m_sel=16'hffff;
    tick();
    if (m_accept || !s_cyc || !s_stb || s_addr != 32'h123)
      $fatal(1, "request was not registered before forwarding");
    @(negedge clk); s_accept=1;
    tick(); s_accept=0;
    if (!m_accept || !s_cyc || s_stb)
      $fatal(1, "acceptance was not returned while holding cycle");
    @(negedge clk); m_stb=0; s_rdata=128'h0123456789abcdef_deadbeefcafef00d; s_ack=1;
    tick(); s_ack=0;
    if (!m_ack || m_rdata != s_rdata)
      $fatal(1, "response did not cross registered boundary");
    tick();
    if (m_ack || s_cyc) $fatal(1, "response/cycle did not retire");
    $display("PASS: wishbone request pipeline"); $finish;
  end
  initial begin #1000; $fatal(1, "pipeline timed out"); end
endmodule
'''


class WishbonePipelineTest(unittest.TestCase):
    def test_registered_request_response_boundary(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="wb-pipeline-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(TB)
            build = subprocess.run(
                ["verilator", "--binary", "--timing", "-Wno-fatal", "-j", "2",
                 "--top-module", "wb_pipeline_tb",
                 str(root / "rtl/memory/llm_wishbone_pipeline.sv"), "tb.sv"],
                cwd=path, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(path / "obj_dir/Vwb_pipeline_tb")],
                                 cwd=path, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: wishbone request pipeline", run.stdout)


if __name__ == "__main__":
    unittest.main()
