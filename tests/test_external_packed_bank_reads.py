"""Execute compiler-lowered packed banks, including delayed completion joins."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import externalize_compiler_memory as em


def fixture(family, width, phases, selectors):
    names = [f"{family}_b{i}" for i in range(25)]
    source = ["""module main(input logic clk, reset, active, mode,
      input logic [4:0] bank, input logic [3:0] address,
      output logic completed, output logic [63:0] selected);
      wire [63:0] slow_data; wire slow_done;
    """]
    for phase, selector in zip(phases, selectors):
        source += [f"wire {phase}_go_out = active && (mode == 1'b{int(phase == phases[1])});",
                   f"wire [4:0] {selector} = bank;",
                   f"wire {phase}_done_in;"]
    source += [f"assign completed = mode ? {phases[1]}_done_in : {phases[0]}_done_in;"]
    for name in names:
        source += [f"wire {name}_done, {name}_content_en; wire [{width-1}:0] {name}_data;",
                   f"assign {name}_content_en = {phases[0]}_go_out | {phases[1]}_go_out;",
                   f"seq_mem_d1 #(.WIDTH({width}), .SIZE(16), .IDX_SIZE(4)) {name} ("
                   f".clk(clk), .reset(reset), .addr0(address), .content_en({name}_content_en),"
                   f".write_en(1'b0), .write_data({width}'d0), .read_data({name}_data), .done({name}_done));"]
    for phase in phases:
        source += [f"assign {phase}_done_in = " + " & ".join(f"{n}_done" for n in names) + " & slow_done;"]
    source += ["assign selected = " + " : ".join(f"bank == 5'd{i} ? {name}_data" for i, name in enumerate(names)) + " : 64'd0;",
               "wire slow_enable;",
               f"assign slow_enable = {phases[0]}_go_out | {phases[1]}_go_out;",
               "seq_mem_d1 #(.WIDTH(64), .SIZE(16), .IDX_SIZE(4)) slow ("
               ".clk(clk), .reset(reset), .addr0(address), .content_en(slow_enable),"
               ".write_en(1'b0), .write_data(64'd0), .read_data(slow_data), .done(slow_done));",
               "endmodule"]
    return "\n".join(source), names + ["slow"]


TB = r'''module tb;
  logic clk=0; always #5 clk=~clk;
  logic reset=1, active=0, mode=0;
  logic [4:0] bank=0;
  logic [3:0] address=0;
  wire completed; wire [63:0] selected;
  wire [25:0] ext_mem_req_valid;
  logic [25:0] ext_mem_req_ready=0, ext_mem_rsp_valid=0;
  wire [831:0] ext_mem_req_addr;
  logic [1663:0] ext_mem_rsp_data=0;
  logic [25:0] expected_requests;
  main dut (.*);
  task tick; @(posedge clk); #1; endtask
  task phase(input logic next_mode, input logic [4:0] next_bank,
             input logic [3:0] next_address, input logic [63:0] value);
    @(negedge clk); mode=next_mode; bank=next_bank; address=next_address; active=1;
    expected_requests=(26'd1 << next_bank) | (26'd1 << 25);
    tick();
    if(ext_mem_req_valid !== expected_requests)
      $fatal(1,"packed phase requested inactive banks: got=%h want=%h",ext_mem_req_valid,expected_requests);
    if(ext_mem_req_addr[next_bank*32 +: 32] !== next_address * (WIDTH/8))
      $fatal(1,"selected bank byte address changed");
    repeat(3) begin tick(); if(ext_mem_req_valid !== expected_requests) $fatal(1,"backpressure lost payload"); end
    @(negedge clk); ext_mem_req_ready=expected_requests;
    tick(); @(negedge clk); ext_mem_req_ready=0;
    ext_mem_rsp_valid=26'd1 << next_bank;
    ext_mem_rsp_data[next_bank*64 +: 64]=value << ((next_address*(WIDTH/8)%8)*8);
    tick(); @(negedge clk); ext_mem_rsp_valid=0;
    repeat(9) begin
      tick();
      if(ext_mem_req_valid) $fatal(1,"selected bank reissued while joined operand pending");
      if(completed) $fatal(1,"completed before delayed operand responded");
    end
    @(negedge clk); ext_mem_rsp_valid=26'd1 << 25;
    ext_mem_rsp_data[25*64 +: 64]=64'hfedcba9876543210;
    tick(); @(negedge clk); ext_mem_rsp_valid=0; tick();
    if(!completed || selected !== value) $fatal(1,"selected bank result/completion wrong");
    @(negedge clk); active=0; repeat(3) tick();
    if(completed || ext_mem_req_valid) $fatal(1,"phase did not drain");
  endtask
  initial begin
    repeat(2) tick(); @(negedge clk); reset=0;
    phase(0,0,0,WIDTH == 64 ? 64'hfedcba9812345678 : 64'h12345678);
    phase(0,24,1,WIDTH == 64 ? 64'habcdef1287654321 : 64'h87654321);
    phase(1,12,2,64'habcdef12);
    phase(1,12,2,64'h98765432);
    @(negedge clk); reset=1; tick(); @(negedge clk); reset=0;
    phase(1,24,3,64'h13579bdf);
    // An unpopulated selector must not issue any bank read or falsely finish.
    @(negedge clk); bank=31; mode=0; active=1;
    tick();
    if(ext_mem_req_valid !== (26'd1 << 25)) $fatal(1,"invalid selector requested a bank");
    @(negedge clk); ext_mem_req_ready=26'd1 << 25;
    tick(); @(negedge clk); ext_mem_req_ready=0; ext_mem_rsp_valid=26'd1 << 25;
    tick(); @(negedge clk); ext_mem_rsp_valid=0;
    repeat(8) begin tick(); if(completed || ext_mem_req_valid) $fatal(1,"invalid selector falsely completed or reissued"); end
    $display("PASS packed selected bank, backpressure, operation isolation, same-address rearm, reset");
    $finish;
  end
  initial begin #20000; $fatal(1,"packed bank test deadline"); end
endmodule
'''


class ExternalPackedBankReadsTest(unittest.TestCase):
    def test_packed_code_and_scale_banks_select_and_isolate_real_requests(self):
        self.assertIsNotNone(shutil.which("iverilog"))
        families = [
            ("token_weight_codes_packed", 64,
             ("lm_gemv_read_operands", "model_read_token_codes"),
             ("lm_gemv_weight_bank_out", "model_token_bank_out")),
            ("token_weight_scale_q8_24", 32,
             ("model_read_token_scale", "model_read_logit_scale"),
             ("model_token_scale_bank_out", "model_logit_scale_bank_out")),
        ]
        for family, width, phases, selectors in families:
            with self.subTest(family=family):
                source, names = fixture(family, width, phases, selectors)
                lowered = em.externalize_memories(source, names).source
                with tempfile.TemporaryDirectory(prefix="packed-bank-real-rtl-") as directory:
                    path = Path(directory)
                    (path / "tb.sv").write_text(lowered + "\n" + TB.replace("WIDTH", str(width)))
                    build = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", "sim", "tb.sv"],
                                           cwd=path, capture_output=True, text=True, timeout=30)
                    self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                    run = subprocess.run(["vvp", "sim"], cwd=path,
                                         capture_output=True, text=True, timeout=10)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
