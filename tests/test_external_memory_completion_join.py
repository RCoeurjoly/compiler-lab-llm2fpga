import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory


FIXTURE = r'''module join_fixture (
  input logic clk,
  input logic reset,
  input logic active,
  input logic mem_a_done,
  input logic mem_b_done,
  input logic local_done,
  output logic operation_go_out,
  output logic operation_done_in
);
  logic operation_go_in;
  logic operation_done_out;
  assign operation_done_out = operation_done_in;
  assign operation_go_in = active && !operation_done_out;
  assign operation_go_out = operation_go_in;
  assign operation_done_in = mem_a_done & mem_b_done & local_done;
endmodule
'''


TESTBENCH = r'''module tb;
  logic clk = 0;
  always #5 clk = ~clk;
  logic reset = 1;
  logic active = 1;
  logic mem_a_done = 0;
  logic mem_b_done = 0;
  logic local_done = 0;
  wire operation_go_out;
  wire operation_done_in;

  join_fixture dut (.*);

  task automatic tick;
    @(posedge clk);
    #1;
  endtask

  initial begin
    repeat (2) tick();
    reset = 0;
    #1;
    if (!operation_go_out) $fatal(1, "first operation did not start");

    mem_a_done = 1; tick(); mem_a_done = 0;
    if (operation_done_in) $fatal(1, "join completed after only operand A");
    repeat (2) tick();
    mem_b_done = 1; tick(); mem_b_done = 0;
    if (operation_done_in) $fatal(1, "join completed before the local operand");
    repeat (3) tick();
    local_done = 1; tick(); local_done = 0;
    if (!operation_done_in || operation_go_out)
      $fatal(1, "staggered operand completions did not release the operation");

    active = 0;
    tick();
    if (operation_done_in)
      $fatal(1, "join state was not cleared when the operation left its go phase");

    active = 1;
    #1;
    if (!operation_go_out) $fatal(1, "second operation did not start cleanly");
    mem_a_done = 1; tick(); mem_a_done = 0;
    local_done = 1; tick(); local_done = 0;
    repeat (3) tick();
    if (operation_done_in)
      $fatal(1, "completion from the previous operation leaked into the next");
    mem_b_done = 1; tick(); mem_b_done = 0;
    if (!operation_done_in)
      $fatal(1, "second staggered operand group did not complete");

    $display("PASS: staggered operand responses join once per generated go phase");
    $finish;
  end
endmodule
'''


class ExternalMemoryCompletionJoinTest(unittest.TestCase):
    def test_completion_join_latches_operands_and_rearms_per_go_phase(self):
        lower = getattr(
            externalize_compiler_memory,
            "latch_external_memory_completion_joins",
            None,
        )
        self.assertIsNotNone(lower, "latency-tolerant completion join lowering is missing")
        lowered = lower(FIXTURE, ["mem_a", "mem_b"])

        verilator = shutil.which("verilator")
        self.assertIsNotNone(verilator, "Verilator is required for the RTL behavior test")
        with tempfile.TemporaryDirectory(prefix="external-memory-join-") as temp_dir:
            temp = Path(temp_dir)
            (temp / "tb.sv").write_text(lowered + "\n" + TESTBENCH, encoding="utf-8")
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
            self.assertIn("PASS: staggered operand responses join", ran.stdout)


if __name__ == "__main__":
    unittest.main()
