from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RTL = ROOT / "rtl" / "tinystories_1m_ddr3_command_adapter.sv"

# A contract test double, never accelerator implementation RTL. It checks the
# adapter's held run controls and prompt wiring, and completes one delayed read.
BEHAVIOR_TB = r'''
module tinystories_1m_ddr3_backend (
 input wire clk, reset, start, valid, token_index,
 input wire [15:0] prompt_0, prompt_1, prompt_2, prompt_3,
 output reg done, output reg [15:0] token_id,
 output wire wb_cyc, wb_stb, wb_we,
 output wire [31:0] wb_addr, output wire [15:0] wb_sel,
 input wire wb_accept, wb_ack, wb_err, input wire [127:0] wb_rdata
);
 reg pending=0, issued=0;
 assign wb_cyc = start && (!issued || pending);
 assign wb_stb = start && !issued;
 assign wb_we=0;
 assign wb_addr=32'd7;
 assign wb_sel=16'hffff;
 always @(posedge clk) begin
  if(reset || !start) begin pending<=0; issued<=0; done<=0; token_id<=0; end
  else begin
   if(!valid || token_index || prompt_0!=7454 || prompt_1!=2402 ||
      prompt_2!=257 || prompt_3!=640) $fatal(1,"adapter changed run contract or prompt");
   if(wb_stb && wb_accept) begin issued<=1; pending<=1; end
   if(pending && wb_ack) begin
    if(wb_err || wb_rdata!=128'h1234) $fatal(1,"response not forwarded");
    pending<=0; done<=1; token_id<=11;
   end
  end
 end
endmodule

module tb;
 reg clk=0; always #5 clk=~clk;
 reg reset=1, clear=0, prompt_valid=0, start=0, token_ready=0;
 reg [15:0] prompt_token=0;
 wire prompt_ready, token_valid, busy, error;
 wire [15:0] token_id;
 wire [7:0] error_code;
 wire [31:0] request_count;
 wire wb_cyc, wb_stb, wb_we;
 wire [31:0] wb_addr;
 wire [15:0] wb_sel;
 reg wb_accept=0, wb_ack=0, wb_err=0;
 reg [127:0] wb_rdata=0;
 tinystories_1m_ddr3_command_adapter dut (.*);
 task tick; @(posedge clk); #1; endtask
 task send(input [15:0] value);
  @(negedge clk);
  if(!prompt_ready) $fatal(1,"prompt not ready");
  prompt_valid=1; prompt_token=value;
  tick(); @(negedge clk); prompt_valid=0;
 endtask
 initial begin
  repeat(2) tick(); @(negedge clk); reset=0;
  start=1; tick(); @(negedge clk); start=0;
  if(!error || error_code!=1 || busy || wb_cyc) $fatal(1,"early start not rejected");
  clear=1; tick(); @(negedge clk); clear=0;
  if(error || error_code || busy || request_count) $fatal(1,"clear did not reset adapter");
  send(7454); send(2402); send(257); send(640);
  if(prompt_ready) $fatal(1,"accepted more than four prompt words");
  start=1; tick(); @(negedge clk); start=0;
  repeat(4) begin
   tick();
   if(!busy || !wb_cyc || !wb_stb || wb_we || wb_addr!=7 || wb_sel!=16'hffff)
    $fatal(1,"request not held through stall");
   if(request_count || token_valid) $fatal(1,"unaccepted request counted/completed");
  end
  @(negedge clk); wb_accept=1;
  tick(); @(negedge clk); wb_accept=0;
  if(request_count!=1) $fatal(1,"accepted request not counted once");
  repeat(7) begin
   tick();
   if(!busy || !wb_cyc || wb_stb || token_valid || request_count!=1)
    $fatal(1,"run/transaction not held until response");
  end
  @(negedge clk); wb_rdata=128'h1234; wb_ack=1;
  tick(); @(negedge clk); wb_ack=0;
  repeat(3) tick();
  repeat(5) begin
   if(!token_valid || token_id!=11 || !busy || prompt_ready)
    $fatal(1,"token not retained under backpressure");
   tick();
  end
  @(negedge clk); token_ready=1;
  tick(); @(negedge clk); token_ready=0;
  if(token_valid || busy || request_count!=1) $fatal(1,"token handshake did not retire");
  clear=1; tick(); @(negedge clk); clear=0;
  if(!prompt_ready || token_valid || busy || request_count || error)
   $fatal(1,"adapter did not rearm");
  $display("PASS: prompt, held run, delayed response, counter and token backpressure");
  $finish;
 end
 initial begin #10000; $fatal(1,"adapter test timed out"); end
endmodule
'''


class TinyStoriesDdr3CommandAdapterContractTest(unittest.TestCase):
    def test_actual_adapter_behaves_under_stall_and_token_backpressure(self):
        self.assertIsNotNone(shutil.which("verilator"))
        with tempfile.TemporaryDirectory(prefix="compiler-command-adapter-") as directory:
            path = Path(directory)
            (path / "tb.sv").write_text(BEHAVIOR_TB, encoding="utf-8")
            build = subprocess.run(
                ["verilator", "--binary", "--timing", "-Wno-fatal", "--top-module", "tb",
                 str(RTL), "tb.sv"], cwd=path, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(path / "obj_dir/Vtb")], cwd=path,
                                 capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS: prompt, held run", run.stdout)

    def test_assembles_prompt_and_holds_core_run(self):
        source = RTL.read_text(encoding="utf-8")
        self.assertIn("prompt_words [0:3]", source)
        self.assertIn("prompt_count == 3'd4", source)
        self.assertIn("assign prompt_ready = !run_active", source)
        self.assertIn(".start(run_active), .valid(run_active)", source)

    def test_exposes_transport_neutral_result_and_wishbone(self):
        source = RTL.read_text(encoding="utf-8")
        for name in ("token_valid", "token_ready", "token_id", "request_count", "wb_cyc", "wb_ack", "wb_rdata"):
            self.assertIn(name, source)


if __name__ == "__main__":
    unittest.main()
