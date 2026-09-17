import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory


TESTBENCH = r"""module tb;
  logic clk = 0;
  always #5 clk = ~clk;
  logic reset = 1;
  logic [1:0] addr0 = 0;
  logic content_en = 0;
  logic done;
  logic [7:0] read_data;
  logic [7:0] write_data = 0;
  logic write_en = 0;
  logic ext_req_valid;
  logic ext_req_ready = 1;
  logic [31:0] ext_req_addr;
  logic ext_rsp_valid = 0;
  logic [63:0] ext_rsp_data = 0;

  seq_mem_d1_external #(.WIDTH(8), .SIZE(4), .IDX_SIZE(2)) dut (.*);

  task automatic tick;
    @(posedge clk);
    #1;
  endtask

  initial begin
    repeat (2) tick();
    reset = 0;
    content_en = 1;
    addr0 = 0;
    tick(); // Capture the request before arbitration.
    if (!ext_req_valid || ext_req_addr != 0)
      $fatal(1, "first read request missing");
    tick();
    if (ext_req_valid)
      $fatal(1, "first request was not accepted into pending state");

    ext_rsp_data = 64'h11;
    ext_rsp_valid = 1;
    tick();
    if (!done || read_data != 8'h11)
      $fatal(1, "first response did not publish data and done");
    ext_rsp_valid = 0;
    tick();
    if (done)
      $fatal(1, "memory completion must be a one-cycle response pulse");
    if (ext_req_valid)
      $fatal(1, "same-address completion caused a duplicate external read");

    // Keep content_en asserted as in a generated streaming memory group, but
    // step to a different address after consuming the first response.
    addr0 = 1;
    tick(); // Capture the next request; do not expose a live address.
    if (!ext_req_valid || ext_req_addr != 1)
      $fatal(1, "second address was not requested");
    tick();
    if (done)
      $fatal(1, "stale done exposed the previous word while the next read is pending");
    if (read_data != 8'h11)
      $fatal(1, "test setup expected the old word while second response is pending");

    repeat (3) begin
      tick();
      if (done)
        $fatal(1, "done asserted before the delayed second response");
    end

    // The response belongs to accepted byte address 1, not the live input.
    // A request pipeline must retain this association through backpressure.
    addr0 = 2;
    ext_rsp_data = 64'h2200;
    ext_rsp_valid = 1;
    tick();
    if (!done || read_data != 8'h22)
      $fatal(1, "second response did not publish its own data and done");
    ext_rsp_valid = 0;
    tick(); // Queue the next address after publishing the previous response.
    if (!ext_req_valid || ext_req_addr != 2)
      $fatal(1, "completion was incorrectly associated with the new input address");
    $display("PASS: done only marks the currently returned streaming word valid");
    $finish;
  end
endmodule
"""


class ExternalMemoryStreamValidityTest(unittest.TestCase):
    def test_done_drops_while_next_streaming_read_is_pending(self):
        verilator = shutil.which("verilator")
        self.assertIsNotNone(verilator, "Verilator is required for the RTL behavior test")

        with tempfile.TemporaryDirectory(prefix="external-memory-validity-") as temp_dir:
            temp = Path(temp_dir)
            (temp / "tb.sv").write_text(
                externalize_compiler_memory._EXTERNAL_MODULE + "\n" + TESTBENCH,
                encoding="utf-8",
            )
            built = subprocess.run(
                [verilator, "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", "tb.sv"],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run(
                [str(temp / "obj_dir" / "Vtb")],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            self.assertIn("PASS: done only marks the currently returned", ran.stdout)


if __name__ == "__main__":
    unittest.main()
