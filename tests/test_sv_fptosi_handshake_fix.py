import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "pipeline" / "fix_sv_fptosi_handshake.py"


FUTIL = """component main() -> () {
  cells {
  }
  wires {
    group bb0_1 {
      fptosi_0_reg.in = std_fpToIntFN_0.out;
      fptosi_0_reg.write_en = 1'b1;
    }
    group bb0_2 {
      fptosi_1_reg.in = std_fpToIntFN_1.out;
      fptosi_1_reg.write_en = 1'b1;
    }
  }
  control { }
}
"""


SV = """module main;
assign bb0_1_done_in = shared_reg_done;
assign bb0_2_done_in = shared_reg_done;
assign shared_reg_write_en =
 other_go_out ? other_done :
 bb0_1_go_out |
 bb0_2_go_out |
 unaffected_go_out ? 1'd1 : 1'd0;
endmodule
"""


def run_tool(tmp_path: Path, futil: str = FUTIL, sv: str = SV):
    futil_path = tmp_path / "model.futil"
    input_path = tmp_path / "input.sv"
    output_path = tmp_path / "output.sv"
    receipt_path = tmp_path / "receipt.json"
    futil_path.write_text(futil)
    input_path.write_text(sv)
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(futil_path),
            str(input_path),
            str(output_path),
            str(receipt_path),
        ],
        text=True,
        capture_output=True,
    )
    return result, output_path, receipt_path


class SvFptosiHandshakeFixTest(unittest.TestCase):
    def test_splits_shared_unconditional_branch_and_records_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            result, output_path, receipt_path = run_tool(Path(directory))

            self.assertEqual(result.returncode, 0, result.stderr)
            output = output_path.read_text()
            self.assertIn("other_go_out ? other_done", output)
            self.assertIn("bb0_1_go_out ? std_fpToIntFN_0_done", output)
            self.assertIn("bb0_2_go_out ? std_fpToIntFN_1_done", output)
            self.assertIn("unaffected_go_out ? 1'd1", output)
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["repair_count"], 2)
            self.assertEqual(receipt["bindings"][0]["group"], "bb0_1")
            self.assertNotEqual(
                receipt["input_sv_sha256"], receipt["output_sv_sha256"]
            )

    def test_second_application_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            first, output_path, _ = run_tool(tmp_path)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_output = output_path.read_text()

            second_dir = tmp_path / "second"
            second_dir.mkdir()
            second, second_output, second_receipt = run_tool(
                second_dir, sv=first_output
            )

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second_output.read_text(), first_output)
            self.assertEqual(
                json.loads(second_receipt.read_text())["repair_count"], 0
            )

    def test_gates_targets_in_plain_or_without_changing_other_enables(self):
        sv = """module main;
assign bb0_1_done_in = shared_reg_done;
assign bb0_2_done_in = shared_reg_done;
assign shared_reg_write_en = bb0_1_go_out |
bb0_2_go_out |
invoke7_go_out;
endmodule
"""
        with tempfile.TemporaryDirectory() as directory:
            result, output_path, receipt_path = run_tool(Path(directory), sv=sv)

            self.assertEqual(result.returncode, 0, result.stderr)
            output = output_path.read_text()
            self.assertIn(
                "(bb0_1_go_out & std_fpToIntFN_0_done)", output
            )
            self.assertIn(
                "(bb0_2_go_out & std_fpToIntFN_1_done)", output
            )
            self.assertIn("invoke7_go_out", output)
            self.assertEqual(
                json.loads(receipt_path.read_text())["repair_count"], 2
            )

    def test_rejects_missing_group_to_physical_register_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            result, output_path, receipt_path = run_tool(
                Path(directory), sv="module main;\nendmodule\n"
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bb0_1", result.stderr)
            self.assertFalse(output_path.exists())
            self.assertFalse(receipt_path.exists())


if __name__ == "__main__":
    unittest.main()
