"""The reference trace must record accepted transfers, not stalled attempts."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TB = r'''
`timescale 1ns/1ps
module tb;
  reg clk=0; always #5 clk=~clk;
  reg reset=1, request_accept=0, response_valid=0;
  reg [31:0] request_addr=0;
  reg [127:0] response_data=0;
  reference_memory_trace trace (.*);
  initial begin
    @(negedge clk); reset=0;
    if ($test$plusargs("unsolicited")) begin
      response_valid=1;
      @(negedge clk); $fatal(1,"unsolicited response was accepted");
    end
    // Changing an address while not accepted must not create trace entries.
    request_addr=7;
    repeat (3) @(negedge clk);
    request_addr=12; request_accept=1;
    @(negedge clk); request_accept=0; request_addr=99;
    @(negedge clk); response_valid=1;
    response_data=128'h00112233445566778899aabbccddeeff;
    @(negedge clk); response_valid=0;
    @(negedge clk); $finish;
  end
endmodule
'''


class ReferenceMemoryTraceTest(unittest.TestCase):
    def test_accepted_address_and_response_are_paired_and_unsolicited_response_fails(self):
        with tempfile.TemporaryDirectory(prefix="reference-memory-trace-") as directory:
            work = Path(directory)
            (work / "tb.sv").write_text(TB)
            build = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(work / "test.vvp"),
                str(ROOT / "sim/compiler_ddr3/reference_memory_trace.sv"), str(work / "tb.sv")],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            good = subprocess.run(["vvp", "-n", str(work / "test.vvp"), "+TRACE_FILE=" + str(work / "good.trace")],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            self.assertEqual((work / "good.trace").read_text(),
                "Q 0 0000000c\nR 0 0000000c 00112233445566778899aabbccddeeff\n")
            bad = subprocess.run(["vvp", "-n", str(work / "test.vvp"), "+TRACE_FILE=" + str(work / "bad.trace"),
                                  "+unsolicited"], capture_output=True, text=True, timeout=30)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("FAIL: unmatched reference response", bad.stdout)


if __name__ == "__main__":
    unittest.main()
