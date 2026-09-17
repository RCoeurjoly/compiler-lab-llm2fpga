"""Arbitration must register selection before accepting a client payload."""

import subprocess
import tempfile
import unittest
from pathlib import Path


TB = r'''
module staged_arbiter_tb;
  logic clk=0; always #5 clk=~clk;
  logic rst=1;
  logic [239:0] req_valid=0;
  wire [239:0] req_ready, rsp_valid;
  logic [7679:0] req_addr=0;
  wire [15359:0] rsp_data;
  wire wb_cyc, wb_stb;
  wire [31:0] wb_addr;
  wire [15:0] wb_sel;
  logic wb_accept=0, wb_ack=0, wb_err=0;
  logic [127:0] wb_rdata=128'h0123456789abcdef_deadbeefcafef00d;
  llm_external_memory_arbiter #(.PORTS(240)) dut (.*);
  task tick; @(posedge clk); #1; endtask
  initial begin
    repeat(2) tick(); @(negedge clk); rst=0;
    req_valid[3]=1; req_valid[239]=1;
    req_addr[3*32+:32]=32'h2b; req_addr[239*32+:32]=32'h48;
    #1;
    if (|req_ready || wb_cyc) $fatal(1,"request bypassed registered selection");
    tick();
    if (!req_ready[3] || $countones(req_ready)!=1 || wb_cyc)
      $fatal(1,"selection did not precede payload acceptance");
    // A new contender cannot replace an already selected requester.
    @(negedge clk); req_valid[0]=1; req_addr[0+:32]=32'h90;
    #1; if (!req_ready[3] || req_ready[0]) $fatal(1,"selection changed before handshake");
    tick();
    if (!wb_cyc || !wb_stb || wb_addr!=2 || |req_ready)
      $fatal(1,"selected payload not captured on handshake");
    @(negedge clk); req_valid[3]=0; req_addr[3*32+:32]=32'hffff;
    repeat(3) begin
      tick();
      if (!wb_cyc || !wb_stb || wb_addr!=2 || |rsp_valid || |req_ready)
        $fatal(1,"Wishbone request changed under backpressure");
    end
    @(negedge clk); wb_accept=1; tick();
    @(negedge clk); wb_accept=0;
    repeat(3) begin
      tick(); if (!wb_cyc || wb_stb || |rsp_valid || |req_ready)
        $fatal(1,"pending request duplicated or completed early");
    end
    @(negedge clk); wb_ack=1; #1;
    if (|rsp_valid) $fatal(1,"response bypassed registration");
    tick();
    if (!rsp_valid[3] || $countones(rsp_valid)!=1 ||
        rsp_data[3*64+:64]!=64'h0123456789abcdef)
      $fatal(1,"response owner or lane lost across stages");
    @(negedge clk); wb_ack=0; tick();
    if (!req_ready[239] || $countones(req_ready)!=1)
      $fatal(1,"round-robin group order changed");
    // Withdrawal is not a handshake and must not consume a fairness turn.
    @(negedge clk); req_valid[239]=0; tick();
    if (wb_cyc || |req_ready) $fatal(1,"withdrawn choice issued a read");
    @(negedge clk); req_valid[239]=1; tick();
    if (!req_ready[239] || $countones(req_ready)!=1)
      $fatal(1,"withdrawal incorrectly advanced round-robin state");
    // Reset during selection must discard the unaccepted choice.
    @(negedge clk); rst=1; req_valid=0; tick();
    if (|req_ready || wb_cyc || |rsp_valid) $fatal(1,"reset leaked a selected request");
    @(negedge clk); rst=0; wb_ack=1; tick();
    if (|req_ready || wb_cyc || |rsp_valid) $fatal(1,"stale completion after reset");
    $display("PASS: registered selection, atomic capture, stalls and reset");
    $finish;
  end
  initial begin #10000; $fatal(1,"staged arbiter timed out"); end
endmodule
'''


class ExternalMemoryArbiterStagingTest(unittest.TestCase):
    def test_selection_capture_and_response_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="arbiter-staging-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(TB)
            build = subprocess.run(
                ["verilator", "--binary", "--timing", "-Wno-fatal", "-j", "2",
                 "--top-module", "staged_arbiter_tb",
                 str(root / "rtl/memory/llm_external_memory_arbiter.sv"), "tb.sv"],
                cwd=path, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(path / "obj_dir/Vstaged_arbiter_tb")],
                                 cwd=path, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: registered selection", run.stdout)
