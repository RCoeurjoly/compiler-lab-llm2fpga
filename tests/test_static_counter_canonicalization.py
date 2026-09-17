"""The counter pass must remove redundant adders without changing priority."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory as em


LIBRARY = """
module std_add #(parameter WIDTH=4)(input [WIDTH-1:0] left,right,
 output [WIDTH-1:0] out);
 assign out=left+right;
endmodule
"""


def fixture():
    source = """module main(input logic [3:0] fsm_out,
 input early_reset_static_seq_go_out, early_reset_static_seq1_go_out,
 input early_reset_static_seq2_go_out, output [3:0] fsm_in);
"""
    for suffix, group in (("", ""), ("1", "1"), ("2", "2")):
        a, g = f"adder{suffix}", f"early_reset_static_seq{group}_go_out"
        source += f"""
wire [3:0] {a}_left, {a}_right, {a}_out;
std_add #(.WIDTH(4)) {a} (.left({a}_left), .right({a}_right), .out({a}_out));
assign {a}_left = {g} ? fsm_out : 4'd0;
assign {a}_right = {g} ? 4'd1 : 4'd0;
"""
    return source + """
assign fsm_in =
 fsm_out != 4'd2 & early_reset_static_seq_go_out ? adder_out :
 fsm_out == 4'd2 & early_reset_static_seq_go_out ? 4'd0 :
 fsm_out != 4'd3 & early_reset_static_seq1_go_out ? adder1_out :
 fsm_out != 4'd4 & early_reset_static_seq2_go_out ? adder2_out : 4'd0;
endmodule
"""


def lower(source):
    return getattr(em, "canonicalize_static_counter", lambda text: text)(source)


class StaticCounterCanonicalizationTest(unittest.TestCase):
    def run_yosys(self, directory, commands):
        self.assertIsNotNone(shutil.which("yosys"))
        result = subprocess.run(["yosys", "-Q", "-T", "-p", commands],
                                cwd=directory, text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_only_one_incrementer_remains_after_lowering(self):
        with tempfile.TemporaryDirectory(prefix="counter-pass-") as directory:
            path = Path(directory)
            (path / "candidate.sv").write_text(LIBRARY + lower(fixture()))
            self.run_yosys(path, "read_verilog -sv candidate.sv; hierarchy -top main; "
                           "proc; flatten; opt; write_json mapped.json")
            cells = json.loads((path / "mapped.json").read_text())["modules"]["main"]["cells"]
            self.assertEqual(sum(c["type"] == "$add" for c in cells.values()), 1,
                             "guarded copies of the same counter increment remain")

    def test_equivalence_includes_overlapping_enables_and_wraparound(self):
        with tempfile.TemporaryDirectory(prefix="counter-equiv-") as directory:
            path = Path(directory)
            (path / "both.sv").write_text(LIBRARY + fixture().replace("module main(", "module gold(")
                + lower(fixture()).replace("module main(", "module gate("))
            self.run_yosys(path, "read_verilog -sv both.sv; hierarchy -check; proc; flatten gold gate; opt; "
                           "equiv_make gold gate equiv; hierarchy -top equiv; "
                           "equiv_simple; equiv_status -assert")

    def test_changed_increment_is_rejected(self):
        with self.assertRaises(ValueError):
            lower(fixture().replace("? 4'd1 :", "? 4'd2 :", 1))

    def test_zero_branch_uses_boolean_truth_not_bitwise_complement(self):
        source = fixture().replace(
            "fsm_out == 4'd2 & early_reset_static_seq_go_out ? 4'd0 :",
            "4'b0010 ? 4'd0 :",
        )
        with tempfile.TemporaryDirectory(prefix="counter-truth-") as directory:
            path = Path(directory)
            (path / "both.sv").write_text(LIBRARY + source.replace("module main(", "module gold(")
                + lower(source).replace("module main(", "module gate("))
            self.run_yosys(path, "read_verilog -sv both.sv; hierarchy -check; proc; flatten gold gate; opt; "
                           "equiv_make gold gate equiv; hierarchy -top equiv; "
                           "equiv_simple; equiv_status -assert")

    def test_changed_operator_is_rejected(self):
        with self.assertRaises(ValueError):
            lower(fixture().replace("std_add #", "std_sub #", 1))

    def test_missing_counter_is_unchanged(self):
        self.assertEqual(lower("module main(); endmodule"), "module main(); endmodule")

    def test_repeated_lowering_preserves_the_candidate(self):
        once = lower(fixture())
        self.assertEqual(lower(once), once)


if __name__ == "__main__":
    unittest.main()
