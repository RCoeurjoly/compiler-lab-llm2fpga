"""Catch consumers advancing past fixed BRAM read windows before DDR replies."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory as em


SCHEDULES = {
    "attention_exp_lut_q1_20": (
        "fsm_out < 4'd2 & early_reset_static_par_thread8_go_out",
        "early_reset_static_par_thread8_go_out", 5, "fsm_out == 2", "12'd4075", 1,
    ),
    "gelu_lut_q12": (
        "(fsm_out < 4'd2 | fsm_out >= 4'd3 & fsm_out < 4'd5) & early_reset_static_seq50_go_out",
        "early_reset_static_seq50_go_out", 7, "fsm_out == 2 || fsm_out == 5",
        "(fsm_out < 3 ? 12'd4075 : 12'd4095)", 2,
    ),
    "prompt_tokens": (
        "cond_wire_out & fsm_out >= 4'd1 & fsm_out < 4'd3 & early_reset_static_seq0_go_out",
        "early_reset_static_seq0_go_out", 5, "fsm_out == 3", "12'd4075", 1,
    ),
}


def fixture(name):
    enable, go, end, consume, index, requests = SCHEDULES[name]
    return f"""
module tb;
logic clk=0; always #5 clk=~clk;
logic reset=1;
logic [3:0] fsm_out=0;
wire fsm_write_en;
wire {go} = !reset && fsm_out < {end};
logic cond_wire_out=1;
wire {name}_content_en;
wire {name}_done;
wire [63:0] data;
wire req;
wire [31:0] addr;
logic rsp=0;
logic [63:0] response_data=0;
integer delay_count=0, latency=7, request_count=0, consumed=0;
assign {name}_content_en = {enable};
assign fsm_write_en = {go};
seq_mem_d1_external #(.WIDTH(64),.SIZE(4096),.IDX_SIZE(12)) lut (
 .clk(clk),.reset(reset),.addr0({index}),.content_en({name}_content_en),
 .done({name}_done),.read_data(data),.write_data(64'd0),.write_en(1'b0),
 .ext_req_valid(req),.ext_req_ready(1'b1),.ext_req_addr(addr),
 .ext_rsp_valid(rsp),.ext_rsp_data(response_data));
always @(posedge clk) begin
 if(reset) fsm_out<=0;
 else if(fsm_write_en) fsm_out<=fsm_out+1;
 if(!reset && ({consume}) && cond_wire_out) begin
  if(data !== (consumed % {requests} == 0 ? 64'hebd69 : 64'hff008))
   $fatal(1,"static schedule consumed stale lookup: %h",data);
  consumed <= consumed+1;
 end
 rsp<=0;
 if(req) begin
  if(delay_count!=0) $fatal(1,"duplicate outstanding lookup");
  if(addr != (request_count % {requests} == 0 ? 32600 : 32760))
   $fatal(1,"wrong lookup address %d",addr);
  request_count<=request_count+1;
  response_data<=addr==32600 ? 64'hebd69 : 64'hff008;
  delay_count<=latency;
 end else if(delay_count>0) begin
  delay_count<=delay_count-1;
  if(delay_count==1) rsp<=1;
 end
end
initial begin
 if ($value$plusargs("latency=%d", latency)) begin end
 repeat(2) @(negedge clk); reset=0;
 repeat(80) @(negedge clk);
 if(fsm_out!={end} || consumed!={requests} || request_count!={requests})
  $fatal(1,"first operation incomplete or duplicate: %d %d %d",fsm_out,consumed,request_count);
 reset=1; repeat(2) @(negedge clk); reset=0;
 repeat(80) @(negedge clk);
 if(fsm_out!={end} || consumed!=2*{requests} || request_count!=2*{requests})
  $fatal(1,"second operation incomplete or duplicate");
 // A disabled conditional prompt read must not deadlock the schedule.
 if ("{name}" == "prompt_tokens") begin
  reset=1; cond_wire_out=0; repeat(2) @(negedge clk); reset=0;
  repeat(20) @(negedge clk);
  if(fsm_out!={end} || request_count!=2) $fatal(1,"disabled read stalled or issued");
 end
 $display("PASS: delayed static reads and repeated operations"); $finish;
end
endmodule
"""


class StaticExternalReadTest(unittest.TestCase):
    def test_unknown_static_schedule_is_rejected(self):
        source = fixture("attention_exp_lut_q1_20").replace("fsm_out < 4'd2 &", "fsm_out < 4'd3 &")
        with self.assertRaisesRegex(ValueError, "unsupported static"):
            em.legalize_static_external_reads(source, ["attention_exp_lut_q1_20"])

    def test_missing_scheduler_is_rejected(self):
        source = fixture("attention_exp_lut_q1_20").replace("assign fsm_write_en", "assign other_write_en")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            em.legalize_static_external_reads(source, ["attention_exp_lut_q1_20"])

    def test_unselected_memories_are_not_changed(self):
        source = fixture("attention_exp_lut_q1_20")
        self.assertEqual(em.legalize_static_external_reads(source, ["other"]), source)

    def test_consumers_wait_for_each_external_read_window(self):
        self.assertIsNotNone(shutil.which("verilator"))
        lower = getattr(em, "legalize_static_external_reads", lambda source, names: source)
        for name in SCHEDULES:
            with self.subTest(memory=name), tempfile.TemporaryDirectory(prefix="static-read-") as directory:
                path = Path(directory)
                (path / "tb.sv").write_text(em._EXTERNAL_MODULE + lower(fixture(name), [name]))
                build = subprocess.run(
                    ["verilator", "--binary", "--timing", "-Wno-fatal", "--top-module", "tb", "tb.sv"],
                    cwd=path, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                for latency in (1, 7, 19):
                    run = subprocess.run(
                        [str(path / "obj_dir/Vtb"), f"+latency={latency}"],
                        cwd=path, capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
