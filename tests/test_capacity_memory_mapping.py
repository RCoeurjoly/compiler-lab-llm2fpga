"""Exercise actual Yosys memory allocation, including a conflicting BRAM hint."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.pipeline.map_flattened_memory_checkpoints import checkpoint_script


class CapacityMemoryMappingTest(unittest.TestCase):
    def test_capacity_banks_map_to_distributed_memory_without_changing_ports(self):
        for name, width, depth, distributed in (
            ("c_fc_weight_codes_i8", 8, 131072, True),
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
