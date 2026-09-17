"""Selected completion must not feed a live bank selector into scheduler go."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis.externalize_compiler_memory import latch_external_memory_completion_joins


FIXTURE = r'''
module fixture(input logic clk, reset, active, bank,
               input logic token_weight_codes_i8_b0_done, token_weight_codes_i8_b1_done,
               output wire go, done);
  wire model_read_token_codes_go_out = active && !done;
  wire model_read_token_codes_done_in;
  assign go = model_read_token_codes_go_out;
  assign done = model_read_token_codes_done_in;
  assign model_read_token_codes_done_in =
    (((bank == 1'b0) & token_weight_codes_i8_b0_done) |
     ((bank == 1'b1) & token_weight_codes_i8_b1_done));
endmodule
module tb;
  logic clk=0; always #5 clk=~clk;
  logic reset=1, active=0, bank=1;
  logic token_weight_codes_i8_b0_done=0, token_weight_codes_i8_b1_done=0;
  wire go, done;
  fixture dut(.*);
  task tick; @(posedge clk); #1; endtask
  initial begin
    repeat(2) tick();
    @(negedge clk); reset=0; active=1;
    // Unselected responses cannot complete the operation.
    token_weight_codes_i8_b0_done=1;
    tick(); if(done || !go) $fatal(1,"unselected bank completed lookup");
    @(negedge clk); token_weight_codes_i8_b0_done=0;
    token_weight_codes_i8_b1_done=1; #1;
    if(done || !go) $fatal(1,"selected completion bypassed register");
    tick(); if(!done || go) $fatal(1,"selected completion not captured");
    @(negedge clk); active=0; token_weight_codes_i8_b1_done=0;
    tick(); if(done) $fatal(1,"completed group did not rearm");
    // A late response outside a group must not arm the next group.
    @(negedge clk); token_weight_codes_i8_b1_done=1;
    tick(); if(done) $fatal(1,"inactive response latched");
    @(negedge clk); token_weight_codes_i8_b1_done=0; bank=0; active=1;
    tick(); if(done || !go) $fatal(1,"stale completion in repeated group");
    @(negedge clk); token_weight_codes_i8_b0_done=1;
    tick(); if(!done || go) $fatal(1,"second bank lookup did not complete");
    @(negedge clk); reset=1;
    tick(); if(done) $fatal(1,"reset retained completion");
    $display("PASS: selected completion registered and rearmed");
    $finish;
  end
  initial begin #1000; $fatal(1,"timeout"); end
endmodule
'''


class SelectedCompletionTest(unittest.TestCase):
    def test_selected_response_cannot_change_scheduler_before_clock(self):
        source = latch_external_memory_completion_joins(
            FIXTURE, ["token_weight_codes_i8_b0", "token_weight_codes_i8_b1"]
        )
        self.assertEqual(latch_external_memory_completion_joins(
            source, ["token_weight_codes_i8_b0", "token_weight_codes_i8_b1"]), source)
        self.assertIsNotNone(shutil.which("verilator"))
        with tempfile.TemporaryDirectory(prefix="selected-completion-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(source)
            build = subprocess.run(
                ["verilator", "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", "tb.sv"],
                cwd=path, capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(path / "obj_dir/Vtb")], cwd=path,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: selected completion", run.stdout)
