"""The compiler request stage must isolate live addresses from arbitration."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory as em


TB = r'''
module tb;
  logic clk=0; always #5 clk=~clk;
  logic reset=1, content_en=0, write_en=0;
  logic [3:0] addr0=0;
  logic [7:0] write_data=0;
  wire done;
  wire [7:0] read_data;
  wire ext_req_valid;
  wire [31:0] ext_req_addr;
  logic ext_req_ready=0, ext_rsp_valid=0;
  logic [63:0] ext_rsp_data=0;
  seq_mem_d1_external #(.WIDTH(8),.SIZE(16),.IDX_SIZE(4),.EXT_BASE_ADDR(16)) dut (.*);
  task tick; @(posedge clk); #1; endtask
  initial begin
    repeat(2) tick(); @(negedge clk); reset=0;
    content_en=1; addr0=5; #1;
    if(ext_req_valid) $fatal(1,"request escaped registration");
    tick();
    if(!ext_req_valid || ext_req_addr!=21) $fatal(1,"request not captured");
    // Once captured, the request is irrevocable except for reset. Live client
    // inputs must not change its payload while the arbiter is backpressured.
    @(negedge clk); addr0=6; content_en=0;
    repeat(3) begin
      tick();
      if(!ext_req_valid || ext_req_addr!=21 || done)
        $fatal(1,"queued request changed under backpressure");
    end
    @(negedge clk); ext_req_ready=1;
    tick(); @(negedge clk); ext_req_ready=0;
    if(ext_req_valid || done) $fatal(1,"accepted request not pending");
    addr0=7; content_en=1;
    repeat(3) begin
      tick();
      if(ext_req_valid || done) $fatal(1,"pending read duplicated or completed early");
    end
    @(negedge clk); ext_rsp_valid=1; ext_rsp_data=64'h0000a50000000000;
    tick();
    if(!done || read_data!=8'ha5) $fatal(1,"response lost captured byte offset");
    @(negedge clk); ext_rsp_valid=0;
    tick();
    if(done || !ext_req_valid || ext_req_addr!=23)
      $fatal(1,"new address confused with completed request");
    // Reset flushes a queued, not yet accepted request.
    @(negedge clk); reset=1; content_en=0;
    tick();
    if(ext_req_valid || done) $fatal(1,"reset did not flush queued request");
    @(negedge clk); reset=0; ext_rsp_valid=1;
    tick();
    if(done || ext_req_valid) $fatal(1,"unsolicited response completed after reset");
    $display("PASS: registered request, stalled snapshot, response offset and reset");
    $finish;
  end
  initial begin #3000; $fatal(1,"request-stage test timed out"); end
endmodule
'''


class RegisteredExternalRequestTest(unittest.TestCase):
    def test_address_capture_enable_has_no_live_client_dependency(self):
        """Catch the measured address-mux/comparison-to-capture-enable path.

        This is a structural timing requirement, not functional equivalence:
        functional request stability is checked separately below.
        """
        self.assertIsNotNone(shutil.which("yosys"))
        with tempfile.TemporaryDirectory(prefix="memory-capture-cone-") as directory:
            path = Path(directory)
            (path / "memory.sv").write_text(em._EXTERNAL_MODULE)
            build = subprocess.run(
                ["yosys", "-Q", "-T", "-p",
                 "read_verilog -sv memory.sv; hierarchy -top seq_mem_d1_external; "
                 "proc; opt; write_json memory.json"],
                cwd=path, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            module = json.loads((path / "memory.json").read_text())["modules"][
                "seq_mem_d1_external"]
            drivers = {}
            for cell in module["cells"].values():
                for port, bits in cell["connections"].items():
                    if cell["port_directions"][port] == "output":
                        for bit in bits:
                            drivers[bit] = cell
            forbidden = {
                bit for port in ("addr0", "content_en", "write_en")
                for bit in module["ports"][port]["bits"]
            }
            def leaves(bit, visited):
                if not isinstance(bit, int) or bit in visited:
                    return set()
                visited.add(bit)
                cell = drivers.get(bit)
                if cell is None or "dff" in cell["type"]:
                    return {bit}
                return set().union(*(
                    leaves(source, visited)
                    for port, bits in cell["connections"].items()
                    if cell["port_directions"][port] == "input"
                    for source in bits
                ))
            for signal in ("queued_address", "request_index"):
                checked = 0
                for bit in module["netnames"][signal]["bits"]:
                    if not isinstance(bit, int):
                        continue
                    cell = drivers[bit]
                    self.assertIn("dff", cell["type"])
                    self.assertIn("EN", cell["connections"])
                    if signal == "queued_address":
                        # Invalid payload is unobservable. Reset must not add
                        # thousands of payload reset/enable routing sinks.
                        self.assertNotIn("SRST", cell["connections"])
                        self.assertNotIn("ARST", cell["connections"])
                        for enable in cell["connections"]["EN"]:
                            self.assertFalse(
                                leaves(enable, set()) & set(module["ports"]["reset"]["bits"]),
                                "queued address enable depends on reset",
                            )
                    for enable in cell["connections"]["EN"]:
                        self.assertFalse(
                            leaves(enable, set()) & forbidden,
                            f"{signal} capture enable depends on live client inputs",
                        )
                    checked += 1
                self.assertGreater(checked, 0)

    def test_request_is_registered_and_stable_until_accepted(self):
        self.assertIsNotNone(shutil.which("verilator"))
        with tempfile.TemporaryDirectory(prefix="registered-memory-request-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(em._EXTERNAL_MODULE + TB)
            build = subprocess.run(
                ["verilator", "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", "tb.sv"],
                cwd=path, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(path / "obj_dir/Vtb")], cwd=path,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: registered request", run.stdout)


if __name__ == "__main__":
    unittest.main()
