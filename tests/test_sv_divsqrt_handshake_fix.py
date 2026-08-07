import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "pipeline" / "fix_sv_divsqrt_handshake.py"


SOURCE = """module std_divSqrtFN(input clk, input reset, input go, output logic [31:0] out, output logic done);
wire inReady, outValid;
divSqrtRecFNToRaw_small unit (
  .inReady(inReady),
  .inValid(go),
  .outValid(outValid)
);
logic done_buf[31:0];
assign done = done_buf[31];
logic start;
assign start = go;
always_ff @(posedge clk) begin
  if (reset) begin
    done_buf <= '{default: 0};
  end else if (start) begin
    done_buf[0] <= 1;
  end else begin
    done_buf[0] <= 0;
  end
end
always_ff @(posedge clk) begin
  if (reset) begin
    done_buf <= '{default: 0};
  end else begin
    for (int i = 1; i < 32; i++) begin
      done_buf[i] <= done_buf[i-1];
    end
  end
end
always_ff @(posedge clk) begin
  if (reset) begin
    out <= 0;
  end else if (outValid) begin
    out <= res_std;
  end
end
endmodule
module untouched; endmodule
"""


def run_tool(directory: Path, source: str = SOURCE):
    source_path = directory / "input.sv"
    output_path = directory / "output.sv"
    receipt_path = directory / "receipt.json"
    source_path.write_text(source)
    result = subprocess.run(
        [sys.executable, str(TOOL), str(source_path), str(output_path), str(receipt_path)],
        text=True,
        capture_output=True,
    )
    return result, output_path, receipt_path


class SvDivSqrtHandshakeFixTest(unittest.TestCase):
    def test_replaces_fixed_delay_with_one_request_state_machine(self):
        with tempfile.TemporaryDirectory() as directory:
            result, output_path, receipt_path = run_tool(Path(directory))
            self.assertEqual(result.returncode, 0, result.stderr)
            output = output_path.read_text()
            self.assertIn(".inValid(llm2fpga_request)", output)
            self.assertIn("LLM2FPGA_BUSY", output)
            self.assertIn("LLM2FPGA_COMPLETE", output)
            self.assertIn("if (!go)", output)
            self.assertIn("if (outValid) begin", output)
            self.assertNotIn("done_buf", output)
            self.assertIn("module untouched; endmodule", output)
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["repair_count"], 1)
            self.assertNotEqual(receipt["input_sv_sha256"], receipt["output_sv_sha256"])

    def test_second_application_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, first_output, _ = run_tool(root)
            self.assertEqual(first.returncode, 0, first.stderr)
            second_root = root / "second"
            second_root.mkdir()
            second, second_output, receipt = run_tool(
                second_root, first_output.read_text()
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second_output.read_bytes(), first_output.read_bytes())
            self.assertEqual(json.loads(receipt.read_text())["repair_count"], 0)

    def test_rejects_unknown_wrapper_shape_without_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            result, output_path, receipt_path = run_tool(
                Path(directory), "module std_divSqrtFN; endmodule\n"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output_path.exists())
            self.assertFalse(receipt_path.exists())


if __name__ == "__main__":
    unittest.main()
