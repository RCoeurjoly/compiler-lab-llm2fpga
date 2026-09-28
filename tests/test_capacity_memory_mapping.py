"""Exercise actual Yosys memory allocation, including a conflicting BRAM hint."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.pipeline.map_flattened_memory_checkpoints import checkpoint_script


class CapacityMemoryMappingTest(unittest.TestCase):
    def test_constant_scale_rom_native_mapping_preserves_values_and_staging(self):
        # Removing ROM-capable mapping must fail here, as must corruption of
        # native INIT data or the enabled/reset two-cycle output interface.
        with tempfile.TemporaryDirectory() as temporary:
            d = Path(temporary)
            (d / "image.hex").write_text("".join(f"{(i * 197 + 65537) & 131071:08x}\n" for i in range(512)))
            (d / "source.sv").write_text(f'''module main(input clk, reset, en,
input [8:0] addr, output reg [31:0] result);
(* ram_style="block" *) reg [31:0] \\token_weight_scale_q8_24_b0.mem [0:511];
reg [8:0] read_addr;
initial $readmemh("{d}/image.hex", \\token_weight_scale_q8_24_b0.mem );
always @(posedge clk) begin
 if(reset) begin read_addr <= 0; result <= 0; end
 else if(en) begin
  read_addr <= addr;
  result <= \\token_weight_scale_q8_24_b0.mem [read_addr];
 end
end
endmodule
''')
            (d / "import.ys").write_text(f"read_verilog -sv {d}/source.sv\nproc\nopt\nmemory_dff\nopt_mem\nopt_clean\nwrite_rtlil {d}/source.il\n")
            self._yosys(d / "import.ys")
            script = checkpoint_script(d / "source.il", d / "mapped.il", "token_weight_scale_q8_24_b0.mem")
            (d / "map.ys").write_text(script + f'''techmap -map +/xilinx/lutrams_xc5v_map.v
write_json {d}/native.json
rename main mapped
write_verilog -noattr {d}/mapped.v
''')
            self._yosys(d / "map.ys")
            cells = json.loads((d / "native.json").read_text())["modules"]["main"]["cells"]
            self.assertTrue(any(c["type"].startswith("RAM") for c in cells.values()))
            unsupported = {c["type"] for c in cells.values()
                           if c["type"].startswith("RAM")} - {"RAM32M", "RAM64M"}
            self.assertFalse(unsupported, f"unsupported nextpnr ROM primitives: {unsupported}")
            self.assertFalse(any(c["type"].startswith("$mem") for c in cells.values()))
            (d / "tb.sv").write_text('''module tb;
reg clk=0, reset=1, en=1; reg [8:0] addr=0;
always #5 clk=~clk;
wire [31:0] golden, actual;
main gold(clk,reset,en,addr,golden);
mapped dut(clk,reset,en,addr,actual);
integer i;
initial begin
 @(negedge clk);
 for(i=0;i<1100;i=i+1) begin
  if ((^golden)===1'bx || actual !== golden)
    $fatal(1,"native data/staging mismatch cycle %0d: %h != %h",i,actual,golden);
  reset=(i==519 || i==1031); en=(i<515 || i%3!=0); addr=i;
  @(negedge clk);
 end
 $display("PASS native ROM values, reset, enables and two-cycle staging"); $finish;
end
endmodule
''')
            data_dir = subprocess.check_output(["yosys-config", "--datdir"], text=True).strip()
            build = subprocess.run([os.environ.get("IVERILOG", "iverilog"), "-g2012", "-s", "tb", "-o", str(d / "test"), str(d / "tb.sv"), str(d / "source.sv"), str(d / "mapped.v"), str(Path(data_dir) / "xilinx/cells_sim.v")], capture_output=True, text=True, timeout=60)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([os.environ.get("VVP", "vvp"), str(d / "test")], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS native ROM", run.stdout)

    def test_capacity_banks_choose_native_memory_without_changing_ports(self):
        for name, width, depth, distributed in (
            ("c_fc_weight_codes_i8", 8, 131072, False),
            ("c_proj_weight_codes_i8", 8, 131072, True),
            *((f"token_weight_scale_q8_24_b{i}", 32, 16384, True) for i in range(4)),
            ("token_weight_codes_i8_b0", 8, 16384, False),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                d = Path(temporary)
                bits = (depth - 1).bit_length()
                (d / "source.sv").write_text(f'''module main(input clk, input wen,
input [{bits-1}:0] addr, input [{width-1}:0] data, output reg [{width-1}:0] result);
(* ram_style="block" *) reg [{width-1}:0] \\{name}.mem [0:{depth-1}];
reg [{bits-1}:0] read_addr;
always @(posedge clk) begin
 read_addr <= addr;
 result <= \\{name}.mem [read_addr];
 if(wen) \\{name}.mem [addr] <= data;
end
endmodule
''')
                (d / "import.ys").write_text(f"read_verilog -sv {d}/source.sv\nproc\nopt\nmemory_dff\nwrite_rtlil {d}/source.il\n")
                self._yosys(d / "import.ys")
                script = checkpoint_script(d / "source.il", d / "mapped.il", name + ".mem")
                (d / "map.ys").write_text(script + f"write_json {d}/mapped.json\n")
                self._yosys(d / "map.ys")
                cells = json.loads((d / "mapped.json").read_text())["modules"]["main"]["cells"]
                types = [c["type"] for c in cells.values()]
                self.assertEqual(any("LUTRAM" in t for t in types), distributed, types[:20])
                self.assertEqual(any("BLOCKRAM" in t for t in types), not distributed)
                if distributed:
                    # Both address and output register widths survive mapping.
                    registered_widths = {int(c["parameters"]["WIDTH"], 2) for c in cells.values()
                                         if c["type"] in ("$dff", "$dffe")}
                    self.assertTrue({bits, width} <= registered_widths, registered_widths)

    def _yosys(self, script):
        run = subprocess.run(["yosys", "-Q", "-T", "-s", str(script)], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout[-4000:] + run.stderr)
