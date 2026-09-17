import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory


FIXTURE = r"""module banked_memory_fixture (
  input logic lm_go,
  input logic token_go,
  input logic [7:0] lm_bank,
  input logic [7:0] token_bank,
  input logic lm_codes_done,
  input logic lm_scale_done,
  input logic bank0_done,
  input logic bank1_done,
  input logic bank2_done,
  input logic [7:0] bank0_data,
  input logic [7:0] bank1_data,
  input logic [7:0] bank2_data,
  output logic bank0_en,
  output logic bank1_en,
  output logic bank2_en,
  output logic lm_operands_done,
  output logic token_codes_done,
  output logic [7:0] lm_weight_data,
  output logic [7:0] token_code_data
);
  wire lm_gemv_read_operands_go_out = lm_go;
  wire model_read_token_codes_go_out = token_go;
  wire [7:0] lm_gemv_weight_bank_out = lm_bank;
  wire [7:0] model_token_bank_out = token_bank;
  wire token_weight_codes_i8_b0_done = bank0_done;
  wire token_weight_codes_i8_b1_done = bank1_done;
  wire token_weight_codes_i8_b2_done = bank2_done;
  logic token_weight_codes_i8_b0_content_en;
  logic token_weight_codes_i8_b1_content_en;
  logic token_weight_codes_i8_b2_content_en;

  assign token_weight_codes_i8_b0_content_en = lm_gemv_read_operands_go_out | model_read_token_codes_go_out;
  assign token_weight_codes_i8_b1_content_en = lm_gemv_read_operands_go_out | model_read_token_codes_go_out;
  assign token_weight_codes_i8_b2_content_en = lm_gemv_read_operands_go_out | model_read_token_codes_go_out;
  assign bank0_en = token_weight_codes_i8_b0_content_en;
  assign bank1_en = token_weight_codes_i8_b1_content_en;
  assign bank2_en = token_weight_codes_i8_b2_content_en;

  assign lm_gemv_read_operands_done_in = lm_codes_done & lm_scale_done &
    token_weight_codes_i8_b0_done & token_weight_codes_i8_b1_done & token_weight_codes_i8_b2_done;
  assign model_read_token_codes_done_in = token_weight_codes_i8_b0_done &
    token_weight_codes_i8_b1_done & token_weight_codes_i8_b2_done;
  assign lm_operands_done = lm_gemv_read_operands_done_in;
  assign token_codes_done = model_read_token_codes_done_in;

  always_comb begin
    case (lm_bank)
      8'd0: lm_weight_data = bank0_data;
      8'd1: lm_weight_data = bank1_data;
      8'd2: lm_weight_data = bank2_data;
      default: lm_weight_data = 8'd0;
    endcase
    case (token_bank)
      8'd0: token_code_data = bank0_data;
      8'd1: token_code_data = bank1_data;
      8'd2: token_code_data = bank2_data;
      default: token_code_data = 8'd0;
    endcase
  end
endmodule
"""


TESTBENCH = r"""module tb;
  logic lm_go, token_go;
  logic [7:0] lm_bank, token_bank;
  logic lm_codes_done, lm_scale_done;
  logic bank0_done, bank1_done, bank2_done;
  logic [7:0] bank0_data, bank1_data, bank2_data;
  wire bank0_en, bank1_en, bank2_en;
  wire lm_operands_done, token_codes_done;
  wire [7:0] lm_weight_data, token_code_data;

  banked_memory_fixture dut (.*);

  initial begin
    lm_go = 1; token_go = 0; lm_bank = 2; token_bank = 0;
    lm_codes_done = 1; lm_scale_done = 1;
    bank0_done = 0; bank1_done = 0; bank2_done = 1;
    bank0_data = 8'h10; bank1_data = 8'h21; bank2_data = 8'h32;
    #1;
    if ({bank2_en, bank1_en, bank0_en} != 3'b100)
      $fatal(1, "LM head read did not request only selected bank 2");
    if (!lm_operands_done)
      $fatal(1, "LM head completion did not follow selected bank 2");
    if (lm_weight_data != 8'h32)
      $fatal(1, "LM head data mux changed while selecting bank 2");
    bank1_done = 1; bank2_done = 0; #1;
    if (lm_operands_done)
      $fatal(1, "unselected bank completion incorrectly completed LM head read");

    lm_go = 0; token_go = 1; lm_bank = 2; token_bank = 0;
    bank0_done = 1; bank1_done = 0; bank2_done = 0; #1;
    if ({bank2_en, bank1_en, bank0_en} != 3'b001)
      $fatal(1, "token lookup did not request only selected bank 0");
    if (!token_codes_done)
      $fatal(1, "token lookup completion did not follow selected bank 0");
    if (token_code_data != 8'h10)
      $fatal(1, "token-code data mux changed while selecting bank 0");

    token_bank = 8'd7; #1;
    if ({bank2_en, bank1_en, bank0_en} != 3'b000 || token_codes_done)
      $fatal(1, "out-of-range token bank must not issue or complete a read");
    $display("PASS: bank-select read enables and selected completion preserve data");
    $finish;
  end
endmodule
"""


class SelectExternalMemoryBankTest(unittest.TestCase):
    def test_only_selected_bank_is_requested_and_controls_completion(self):
        transform = getattr(externalize_compiler_memory, "select_banked_memory_reads", None)
        self.assertIsNotNone(transform, "bank-selection lowering is not implemented")
        transformed = transform(FIXTURE)
        self.assertEqual(transform(transformed), transformed)

        verilator = shutil.which("verilator")
        self.assertIsNotNone(verilator, "Verilator is required for the RTL behavior test")
        with tempfile.TemporaryDirectory(prefix="bank-select-rtl-") as temp_dir:
            temp = Path(temp_dir)
            (temp / "fixture.sv").write_text(transformed + "\n" + TESTBENCH)
            built = subprocess.run(
                [verilator, "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", "fixture.sv"],
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
            self.assertIn("PASS: bank-select read enables", ran.stdout)


if __name__ == "__main__":
    unittest.main()
