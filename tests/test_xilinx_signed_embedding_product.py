"""Removing the DSP policy must not silently corrupt negative embeddings.

Runs real synthesis and simulation, not source-text assertions. Optional tools
can be supplied through IVERILOG/VVP; Python itself is run inside Nix.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/xilinx_signed_embedding_product.sv'
POLICY = ROOT / 'fpga/synthesis/tinystories_signed_dsp_policy.ys'


class SignedEmbeddingProductTest(unittest.TestCase):
    def run_mapping(self, width, signed_scale):
        tools = {name: os.environ.get(name.upper()) or shutil.which(name)
                 for name in ('yosys', 'yosys-config', 'iverilog', 'vvp')}
        if not all(tools.values()):
            self.skipTest('requires yosys, yosys-config, iverilog and vvp')
        def run(args, cwd, timeout=60):
            result = subprocess.run(args, cwd=cwd, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=timeout)
            self.assertEqual(result.returncode, 0, result.stdout[-12000:])
            return result.stdout
        datdir = run([tools['yosys-config'], '--datdir'], ROOT).strip()
        with tempfile.TemporaryDirectory(prefix='signed-embedding-') as temp:
            work = Path(temp)
            script = work / 'synth.ys'
            script.write_text(f'''read_verilog -sv {FIXTURE}
chparam -set SCALE_WIDTH {width} -set SIGNED_SCALE {signed_scale} signext_fixture
script {POLICY}
synth_xilinx -family xc7 -top signext_fixture -flatten -noiopad -noclkbuf -abc9 -run begin:coarse
synth_xilinx -family xc7 -top signext_fixture -noiopad -noclkbuf -abc9 -run map_ffram:map_ffs
synth_xilinx -family xc7 -top signext_fixture -noiopad -noclkbuf -run map_ffs:
rename signext_fixture mapped_fixture
write_verilog -noattr mapped.v
''')
            run([tools['yosys'], '-Q', '-T', str(script)], work)
            scales = ('0,1,128,255,256,16384,18141,32767' if width == 15 else
                      "0,1,128,255,256,36794,32'h7fffffff,32'h80000000").split(',')
            assignments = '\n'.join(f'scales[{i}]={v};' for i, v in enumerate(scales))
            scale_expr = "$signed(scale)" if signed_scale else "$signed({1'b0,scale})"
            tb = work / 'tb.sv'
            tb.write_text(f'''`timescale 1ns/1ps
module tb;
reg clk=0,reset=1,go=0; reg signed [7:0] code;
reg [{width-1}:0] scale,scales[0:7];
wire [63:0] gold,actual; wire gd,ad;
reg signed [63:0] expected,wide_scale;
integer i,j,count=0;
always #5 clk=~clk;
signext_fixture #(.SCALE_WIDTH({width}),.SIGNED_SCALE({signed_scale})) reference
 (clk,reset,go,code,scale,gold,gd);
mapped_fixture mapped(clk,reset,go,code,scale,actual,ad);
initial begin
{assignments}
code=0;scale=0;repeat(4)@(negedge clk);reset=0;
for(j=0;j<8;j=j+1)for(i=-128;i<128;i=i+1)begin
 code=i;scale=scales[j];go=1;
 wide_scale={scale_expr};
 expected=i*wide_scale;
 repeat(5)@(negedge clk);
 if(gold!==expected || actual!==expected || gd!==ad)
  $fatal(1,"signed mismatch code=%0d scale=%h expected=%h actual=%h",i,scale,expected,actual);
 count=count+1;go=0;repeat(2)@(negedge clk);
 if(actual!==expected)$fatal(1,"idle retention mismatch");
end
reset=1;repeat(4)@(negedge clk);
if(actual!==0 || gold!==0)$fatal(1,"reset mismatch");
$display("PASS 2048 combinations, idle, reset");$finish;
end
endmodule
''')
            run([tools['iverilog'], '-g2012', '-s', 'tb', '-o', 'test', str(tb),
                 str(FIXTURE), str(work / 'mapped.v'),
                 str(Path(datdir) / 'xilinx/cells_sim.v')], work)
            output = run([tools['vvp'], str(work / 'test')], work)
            self.assertIn('PASS 2048 combinations, idle, reset', output)

    def test_position_product_keeps_sign_extension(self):
        self.run_mapping(15, 0)

    def test_token_product_keeps_sign_extension(self):
        self.run_mapping(32, 1)


if __name__ == '__main__':
    unittest.main()
