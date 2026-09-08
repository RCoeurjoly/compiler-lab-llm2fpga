"""Run the production denominator update with actual two-cycle memory timing."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from scripts.pipeline import run_bram_production_sv as runner

ROOT = Path(__file__).resolve().parents[1]


class AttentionDenominatorTest(unittest.TestCase):
    def test_one_probability_is_accumulated_once(self):
        base = runner.production.base
        block, attention, mlp = base._dependencies()
        phases = base._block_phases(block, attention, mlp, narrow_products=True)
        wires = "\n".join(w for _, ws, _ in phases for w in ws)
        groups = []
        names = ["causal_write_exp_accumulate_denominator"]
        if "group model_accumulate_denominator {" in wires:
            names.append("model_accumulate_denominator")
        for name in names:
            match = re.search(r"group " + name + r" \{(.*?)\n\s*\}", wires, re.S)
            self.assertIsNotNone(match)
            groups.append(match[0])
        futil = '''import "primitives/core.futil";
import "primitives/memories/seq.futil";
component main(@go go: 1) -> (@done done: 1, result: 64) {
cells {
causal_delta = std_reg(64);
causal_delta_is_zero = std_eq(64);
causal_probability_select = std_mux(64);
causal_denominator = std_reg(64);
causal_denominator_add = std_add(64);
causal_slot_address = std_add(10);
attention_exp_lut_q1_20 = seq_mem_d1(64,4096,12);
@external attention_exp_q1_20 = seq_mem_d1(64,1024,10);
}
wires {
result = causal_denominator.out;
causal_slot_address.left = 10'd0;
causal_slot_address.right = 10'd0;
group init {
causal_delta.in = 64'd0; causal_delta.write_en = 1'd1;
causal_denominator.in = 64'd0; causal_denominator.write_en = 1'd1;
init[done] = causal_denominator.done;
}
''' + "\n".join(groups) + "\n}\ncontrol { seq { init; " + " ".join(n + ";" for n in names) + " } }\n}\n"
        tb = '''module tb;
reg clk=0, reset=1, go=0; wire done; wire [63:0] result;
always #5 clk=~clk;
main dut(.clk(clk),.reset(reset),.go(go),.done(done),.result(result));
initial begin
repeat(3) @(negedge clk); reset=0; go=1;
wait(done); @(negedge clk);
if(result !== 64'd1048576) $fatal(1,"denominator repeated: %0d",result);
if(dut.attention_exp_q1_20.mem[0] !== 64'd1048576) $fatal(1,"probability write lost");
$display("PASS denominator accumulated once"); $finish;
end
initial begin #10000; $fatal(1,"timeout"); end
endmodule
'''
        install = Path(subprocess.check_output(["nix","build","--no-link","--print-out-paths",".#calyx"],cwd=ROOT,text=True,timeout=120).strip())
        iverilog = os.environ.get("IVERILOG", shutil.which("iverilog"))
        vvp = os.environ.get("VVP", shutil.which("vvp"))
        self.assertTrue(iverilog and vvp, "Icarus required")
        with tempfile.TemporaryDirectory() as temporary:
            d = Path(temporary)
            library = runner.prepare_production_library(install,d/"library")
            (d/"model.futil").write_text(futil)
            (d/"tb.sv").write_text(tb)
            c = subprocess.run([str(install/"bin/calyx"),str(d/"model.futil"),"-l",str(library),"-d","cell-share","-b","verilog","--synthesis","--nested"],capture_output=True,text=True,timeout=30)
            self.assertEqual(c.returncode,0,c.stderr)
            (d/"model.sv").write_text(runner.annotate_bram_memories(c.stdout))
            b = subprocess.run([iverilog,"-g2012","-s","tb","-o",str(d/"test"),str(d/"model.sv"),str(d/"tb.sv")],capture_output=True,text=True,timeout=30)
            self.assertEqual(b.returncode,0,b.stderr)
            r = subprocess.run([vvp,str(d/"test")],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
