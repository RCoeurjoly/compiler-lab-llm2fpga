"""Exercise narrowed production GEMV arithmetic using real Q-projection operands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.pipeline.run_bram_production_sv import production

ROOT = Path(__file__).resolve().parents[1]


class NarrowGemvExecutionTest(unittest.TestCase):
    def test_activation_scale_reaches_narrowed_mac(self):
        install = Path(subprocess.check_output(["nix", "build", "--no-link", "--print-out-paths", ".#calyx"], cwd=ROOT, text=True, timeout=120).strip())
        mlp = production.base._dependencies()[2]
        cells, wires, control = mlp._gemv_phase("gemv", "codes", "scales", "weights", "trace", 4, 4, 4, narrow_products=True)
        futil = '''import "primitives/core.futil";
import "primitives/binary_operators.futil";
import "primitives/memories/seq.futil";
component main(@go go: 1) -> (@done done: 1, result: 64) {
cells {
codes = seq_mem_d1(8,16,4);
scales = seq_mem_d1(64,4,2);
weights = seq_mem_d1(8,16,4);
@external trace = seq_mem_d1(64,16,4);
''' + "\n".join(cells) + "\n}\nwires {\nresult = gemv_accumulator.out;\n" + "\n".join(wires) + "\n}\ncontrol {\n" + control + "\n}\n}\n"
        tb = '''module tb;
reg clk=0, reset=1, go=0;
wire done; wire [63:0] result;
always #5 clk=~clk;
main dut(.clk(clk),.reset(reset),.go(go),.done(done),.result(result));
integer i;
initial begin
  for(i=0;i<4;i=i+1) begin
    dut.codes.mem[i*4]=96; dut.codes.mem[i*4+1]=-99;
    dut.codes.mem[i*4+2]=-54; dut.codes.mem[i*4+3]=12;
    dut.weights.mem[i*4]=-5; dut.weights.mem[i*4+1]=65;
    dut.weights.mem[i*4+2]=45; dut.weights.mem[i*4+3]=-12;
  end
  dut.scales.mem[0]=359123; dut.scales.mem[1]=291962;
  dut.scales.mem[2]=389147; dut.scales.mem[3]=346639;
  repeat(3) @(negedge clk); reset=0; go=1;
  wait(done); @(negedge clk);
  if(result !== -64'sd3046697736) $fatal(1,"wrong narrowed MAC: %0d",$signed(result));
  for(i=0;i<16;i=i+1)
    if(dut.trace.mem[i] !== -64'sd3046697736) $fatal(1,"wrong trace entry %0d",i);
  $display("PASS exact narrowed MAC"); $finish;
end
initial begin #100000; $fatal(1,"timeout"); end
endmodule
'''
        iverilog = os.environ.get("IVERILOG", shutil.which("iverilog"))
        vvp = os.environ.get("VVP", shutil.which("vvp"))
        self.assertTrue(iverilog and vvp, "Icarus required")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "model.futil").write_text(futil)
            (directory / "tb.sv").write_text(tb)
            compiled = subprocess.run([str(install / "bin/calyx"), str(directory / "model.futil"), "-l", str(install / "share/calyx"), "-d", "cell-share", "-b", "verilog", "--synthesis", "--nested"], check=True, capture_output=True, text=True, timeout=30)
            (directory / "model.sv").write_text(compiled.stdout)
            built = subprocess.run([iverilog,"-g2012","-s","tb","-o",str(directory / "test"),str(directory / "model.sv"),str(directory / "tb.sv")], capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([vvp,str(directory / "test")], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
