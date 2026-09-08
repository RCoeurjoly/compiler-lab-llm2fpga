"""Catch consumption of only the final GEMV accumulator by production argmax."""
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.pipeline import run_bram_production_sv as runner

ROOT = Path(__file__).resolve().parents[1]


class StreamedLmHeadExecutionTest(unittest.TestCase):
    def test_each_vocabulary_accumulator_reaches_its_own_logit(self):
        self._run_head(pin_bank=True)

    def test_bank_selector_remains_valid_through_multiply(self):
        self._run_head(pin_bank=False)

    def test_vocabulary_projection_crosses_a_weight_bank_boundary(self):
        self._run_head(pin_bank=False, cross_bank=True)

    def _run_head(self, *, pin_bank, cross_bank=False):
        artifact = runner.production.generate_production_kernel(generation_steps=1)
        declarations, control = artifact.futil.split("  control {", 1)
        # Execute the actual generated LM-head schedule, omitting upstream work.
        # Four vocabulary entries suffice to distinguish per-entry consumption
        # from reusing the last accumulator. Tensor width remains the real 64.
        start = min(control.index("lm_gemv_init_row;"), control.index("model_init_greedy;"))
        end = control.index("model_commit_feedback;")
        declarations = declarations.replace("token_id = model_token_select.out;", "token_id = model_best_token.out;")
        selected_control = "seq { model_init_length; " + control[start:end] + " }"
        declarations = re.sub(r"(?:comb )?group (\w+) \{[^{}]*\}",
                              lambda m: m[0] if re.search(r"\b" + m[1] + r"\b", selected_control) else "",
                              declarations)
        futil = declarations + "  control { " + selected_control + " }\n}\n"
        futil = futil.replace("16'd50257", "16'd260" if cross_bank else "16'd4")
        if cross_bank:
            # Execute entries 252..259: four on either side of the real
            # 256-token bank boundary, without spending cycles on its prefix.
            futil = futil.replace("lm_gemv_output_counter.in = 16'd0;", "lm_gemv_output_counter.in = 16'd252;")
        # Isolate argmax from the separate bank-selector lifetime defect:
        # this four-entry fixture uses bank zero exclusively.
        if pin_bank:
            futil = futil.replace("lm_gemv_weight_bank.in = lm_gemv_weight_bank_full.out;", "")
            futil = futil.replace("  wires {", "  wires {\nlm_gemv_weight_bank.in = 22'd0;")
        tb = '''module tb;
reg clk=0, reset=1, start=0; wire done; wire [15:0] token_id;
always #5 clk=~clk;
main dut(.clk(clk),.reset(reset),.start(start),.valid(1'b1),
 .token_index(1'b0),.prompt_0(16'd0),.prompt_1(16'd0),
 .prompt_2(16'd0),.prompt_3(16'd0),.done(done),.token_id(token_id));
integer i;
initial begin
 for(i=0;i<64;i=i+1) begin
  dut.lm_input_codes_i8.mem[192+i]=1;
  dut.lm_input_scale_q8_24.mem[i]=16777216;
  dut.token_weight_codes_i8_b0.mem[i]=1;
  dut.token_weight_codes_i8_b0.mem[64+i]=3;
  dut.token_weight_codes_i8_b0.mem[128+i]=7;
  dut.token_weight_codes_i8_b0.mem[192+i]=-2;
 end
 dut.token_weight_scale_q8_24_b0.mem[0]=256;
 dut.token_weight_scale_q8_24_b0.mem[1]=512;
 dut.token_weight_scale_q8_24_b0.mem[2]=256;
 dut.token_weight_scale_q8_24_b0.mem[3]=256;
 repeat(3) @(negedge clk); reset=0; start=1;
 wait(done); @(negedge clk);
 // Hand-derived logits: [64,384,448,-128], not a scale-only argmax.
 if(token_id !== 16'd2) $fatal(1,"wrong streamed argmax: %0d",token_id);
 $display("PASS per-vocabulary accumulator consumption"); $finish;
end
initial begin #1000000; $fatal(1,"timeout row=%0d output=%0d k=%0d best=%0d acc=%0d context=%0d input=%0d scale=%0d",dut.lm_gemv_row_counter.out,dut.lm_gemv_output_counter.out,dut.lm_gemv_k_counter.out,dut.model_best_token.out,$signed(dut.lm_gemv_accumulator.out),dut.model_context_length.out,dut.lm_input_codes_i8.read_data,dut.lm_input_scale_q8_24.read_data); end
endmodule
'''
        if cross_bank:
            # First bank's sampled logits are zero. The next bank contains the
            # same four hand-derived logits, so vocabulary entry 258 wins.
            tb = tb.replace("token_weight_codes_i8_b0.mem", "token_weight_codes_i8_b1.mem")
            for i in range(4):
                tb = tb.replace(f"token_weight_scale_q8_24_b0.mem[{i}]", f"token_weight_scale_q8_24_b0.mem[{256+i}]")
            tb = tb.replace("initial begin\n for", "initial begin\n for(i=0;i<16384;i=i+1) dut.token_weight_codes_i8_b0.mem[i]=0;\n for(i=0;i<256;i=i+1) dut.token_weight_scale_q8_24_b0.mem[i]=256;\n for", 1)
            tb = tb.replace("16'd2)", "16'd258)").replace("#1000000;", "#10000000;")
        install = Path(subprocess.check_output(["nix", "build", "--no-link", "--print-out-paths", ".#calyx"], cwd=ROOT, text=True, timeout=120).strip())
        iverilog = os.environ.get("IVERILOG", shutil.which("iverilog"))
        vvp = os.environ.get("VVP", shutil.which("vvp"))
        self.assertTrue(iverilog and vvp, "Icarus required")
        with tempfile.TemporaryDirectory() as temporary:
            d = Path(temporary)
            library = runner.prepare_production_library(install, d / "library")
            (d / "model.futil").write_text(futil)
            (d / "tb.sv").write_text(tb)
            c = subprocess.run([str(install / "bin/calyx"), str(d / "model.futil"), "-l", str(library), "-d", "cell-share", "-b", "verilog", "--synthesis", "--nested"], capture_output=True, text=True, timeout=60)
            self.assertEqual(c.returncode, 0, c.stderr)
            (d / "model.sv").write_text(runner.annotate_bram_memories(c.stdout))
            b = subprocess.run([iverilog, "-g2012", "-s", "tb", "-o", str(d / "test"), str(d / "model.sv"), str(d / "tb.sv")], capture_output=True, text=True, timeout=60)
            self.assertEqual(b.returncode, 0, b.stderr)
            r = subprocess.run([vvp, str(d / "test")], capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
