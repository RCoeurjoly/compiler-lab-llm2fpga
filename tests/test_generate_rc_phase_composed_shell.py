"""Behavioral integration test for the compiler-owned three-phase shell."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.generate_rc_phase_composed_shell import render_shell, write_package


LOGITS = (
    (0x00000000, 0xBF800000, 0x40000000, 0x40000000, 0xC0000000, 0x3F800000),
    (0xC0400000, 0xC0000000, 0xBF800000, 0x40400000, 0x40400000, 0x00000000),
    (0xBF800000, 0xC0000000, 0xC0400000, 0x3F800000, 0x40800000, 0x40800000),
)
CACHE = (
    (0x80000000, 0xBF800000, 0x7F7FFFFF, 0x00000001),
    (0x01020304, 0x81020304, 0x7F000001, 0x00ABCDEF),
    (0x11111111, 0x22222222, 0x33333333, 0x44444444),
)
STARTS = ((0, 1, (7, 23, 39, 55)), (71, 72, (78, 96, 114, 132)),
          (150, 151, (157, 177, 197, 217)))


def small_manifest() -> dict:
    phases = []
    for index, (token_addr, _, cache_starts) in enumerate(STARTS):
        length = 8 + index
        token_port = 31 if index == 0 else 27
        ports = [{"port": number, "width": 8, "depth": 1} for number in range(37)]
        ports[0] = {"port": 0, "width": 64, "depth": 8 if index == 0 else 1}
        ports[token_port] = {"port": token_port, "width": 64, "depth": 8 if index == 0 else 1}
        ports[32] = {"port": 32, "width": 32, "depth": 48 if index == 0 else 6}
        for leaf in range(4):
            if index:
                ports[28 + leaf] = {"port": 28 + leaf, "width": 32, "depth": 2 * (length - 1)}
            ports[33 + leaf] = {"port": 33 + leaf, "width": 32, "depth": 2 * length}
        phases.append({
            "name": ("prefill-8", "decode-8", "decode-9")[index],
            "top": f"synthetic_phase{index}", "token_input_port": token_port,
            "token_input_words": 8 if index == 0 else 1,
            "token_address": token_addr,
            "logits": {"port": 32, "offset": 42 if index == 0 else 0, "words": 6},
            "cache_outputs": [{"leaf": leaf, "port": 33 + leaf, "width": 32,
                               "words": 2 * length, "readback_address": cache_starts[leaf]}
                              for leaf in range(4)],
            "rtl_memories": ports,
            "initial_memories": {},
        })
    handoffs = []
    for index in (0, 1):
        handoffs.append({
            "source": phases[index]["name"], "destination": phases[index + 1]["name"],
            "token_source_port": 32, "token_destination_port": 27,
            "cache": [{"source_port": 33 + leaf, "destination_port": 28 + leaf,
                       "width": 32, "words": 16 + index * 2} for leaf in range(4)],
        })
    return {"schema": "llm2fpga.rc-phase-handoff-v1", "phase_order": [p["name"] for p in phases],
            "readback_words": 237, "phases": phases, "handoffs": handoffs,
            "readback": [{"phase": p["name"], "start_address": start[0],
                          "word_count": (71, 79, 87)[index]}
                         for index, (p, start) in enumerate(zip(phases, STARTS))]}


def synthetic_phase(phase: dict, phase_index: int) -> str:
    """Small functional memory-handshake client; no transformer arithmetic."""
    ports = ["input logic clk", "input logic reset", "input logic go", "output logic done"]
    assignments = []
    for memory in phase["rtl_memories"]:
        number, width, depth = (memory[key] for key in ("port", "width", "depth"))
        address_width = max(1, (depth - 1).bit_length())
        stem = f"arg_mem_{number}_"
        ports += [f"output logic [{address_width - 1}:0] {stem}addr0",
                  f"output logic {stem}content_en", f"output logic {stem}write_en",
                  f"output logic [{width - 1}:0] {stem}write_data",
                  f"input logic [{width - 1}:0] {stem}read_data", f"input logic {stem}done"]
        read_port = number == phase["token_input_port"] or (phase_index > 0 and 28 <= number <= 31)
        if number == 32:
            assignments += [f"assign {stem}addr0 = {phase['logits']['offset']} + step - 2;",
                            f"assign {stem}content_en = go && step >= 2 && step < 8;",
                            f"assign {stem}write_en = 1'b1;",
                            f"assign {stem}write_data = logit_data;"]
        elif 33 <= number <= 36:
            assignments += [f"assign {stem}addr0 = '0;",
                            f"assign {stem}content_en = go && step == 2;",
                            f"assign {stem}write_en = 1'b1;",
                            f"assign {stem}write_data = 32'h{CACHE[phase_index][number - 33]:08x};"]
        elif read_port:
            address = 7 if phase_index == 0 and number == 31 else 0
            assignments += [f"assign {stem}addr0 = {address};",
                            f"assign {stem}content_en = go && step == 0;",
                            f"assign {stem}write_en = 1'b0;",
                            f"assign {stem}write_data = '0;"]
        else:
            assignments += [f"assign {stem}addr0 = '0;", f"assign {stem}content_en = 1'b0;",
                            f"assign {stem}write_en = 1'b0;", f"assign {stem}write_data = '0;"]
    cases = "\n".join(f"  {index + 2}: logit_data = 32'h{word:08x};"
                      for index, word in enumerate(LOGITS[phase_index]))
    expected_token_input = (1, 2, 3)[phase_index]
    token = phase["token_input_port"]
    checks = [f"if (!arg_mem_{token}_done || arg_mem_{token}_read_data !== 64'd{expected_token_input}) "
              f"$fatal(1, \"phase {phase_index} token input\");"]
    if phase_index:
        checks += [f"if (!arg_mem_{28 + leaf}_done || arg_mem_{28 + leaf}_read_data !== "
                   f"32'h{CACHE[phase_index - 1][leaf]:08x}) "
                   f"$fatal(1, \"phase {phase_index} cache {leaf}\");"
                   for leaf in range(4)]
    return "\n".join([
        f"module {phase['top']}(" + ",\n".join(ports) + ");",
        "logic [3:0] step; logic [31:0] logit_data;",
        "always_ff @(posedge clk) begin",
        "  if (reset) step <= 0;",
        "  else if (go && step < 8) step <= step + 1;",
        "`ifndef SYNTHESIS",
        "  if (!reset && go && step == 1) begin", *checks, "  end",
        "`endif",
        "end",
        "assign done = step == 8;",
        "always_comb begin case(step)", cases, "  default: logit_data = 0;", "endcase end",
        *assignments, "endmodule",
    ])


def synthetic_testbench() -> str:
    expected = {0: 2, 71: 3, 150: 4}
    for phase_index, (_, logits_start, cache_starts) in enumerate(STARTS):
        for word, value in enumerate(LOGITS[phase_index]):
            expected[logits_start + word] = value
        for leaf, address in enumerate(cache_starts):
            expected[address] = CACHE[phase_index][leaf]
    cases = "\n".join(f"  8'd{address}: expected = 64'h{value:016x};"
                      for address, value in sorted(expected.items()))
    return "\n".join([
        "`timescale 1ns/1ps",
        "module tb;",
        "logic clk = 0, reset = 1, prompt_write = 0, start = 0;",
        "logic [2:0] prompt_index = 0; logic [63:0] prompt_data = 0;",
        "logic [7:0] readback_addr = 0; wire [63:0] readback_data;",
        "wire busy, done, error; wire [63:0] token0, token1, token2;",
        "always #5 clk = ~clk;",
        "rc_phase_composed dut(.*);",
        "function automatic [63:0] expected(input [7:0] address);",
        "  case(address)", cases, "  default: expected = 0;", "  endcase", "endfunction",
        "task automatic load_prompt;",
        "  for (int i=0; i<8; i++) begin",
        "    @(negedge clk); prompt_write=1; prompt_index=i[2:0];",
        "    prompt_data=(i==6)?0:((i==7)?1:i);",
        "  end",
        "  @(negedge clk); prompt_write=0;",
        "endtask",
        "initial begin",
        "  repeat(3) @(negedge clk); reset=0; load_prompt();",
        "  @(negedge clk); start=1; @(negedge clk); start=0;",
        "  wait(token0 == 2);",
        "  @(negedge clk); reset=1; @(negedge clk); reset=0;",
        "  if (done || error || token0 != 0 || token1 != 0 || token2 != 0) $fatal(1, \"reset isolation\");",
        "  load_prompt();",
        "  @(negedge clk); start=1; @(negedge clk); start=0;",
        "  if (!busy) $fatal(1, \"not busy after start\");",
        "  @(negedge clk); start=1; @(negedge clk); start=0;",
        "  if (!error) $fatal(1, \"busy start not rejected\");",
        "  for (int cycles=0; cycles<500 && !done; cycles++) @(negedge clk);",
        "  if (!done || busy || token0 != 2 || token1 != 3 || token2 != 4) $fatal(1, \"token sequence\");",
        "  for (int a=0; a<237; a++) begin",
        "    readback_addr=a[7:0]; #1;",
        "    if (readback_data !== expected(a[7:0])) $fatal(1, \"readback %0d got %h expected %h\", a, readback_data, expected(a[7:0]));",
        "  end",
        "  $display(\"PASS rc synthetic 237 words tokens=2,3,4\"); $finish;",
        "end",
        "initial begin #100000; $fatal(1, \"simulation timeout\"); end",
        "endmodule",
    ])


class ComposedShellTests(unittest.TestCase):
    def test_rejects_wrong_token_feedback_port(self):
        manifest = small_manifest()
        manifest["handoffs"][0]["token_destination_port"] = 0
        with self.assertRaisesRegex(ValueError, "token feedback"):
            render_shell(manifest)

    def test_package_rejects_stale_source_before_writing_output(self):
        manifest = small_manifest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {}
            for phase in manifest["phases"]:
                source = root / f"{phase['name']}.sv"
                source.write_text(f"module {phase['top']}; endmodule\n")
                phase["namespaced_sv_sha256"] = "f" * 64
                sources[phase["name"]] = source
            target = root / "package"
            with self.assertRaisesRegex(ValueError, "source hash"):
                write_package(manifest, sources, target)
            self.assertFalse((target / "rc_phase_composed.sv").exists())

    def test_package_records_source_and_memory_hashes(self):
        manifest = small_manifest()
        manifest["phases"][0]["initial_memories"]["31"] = {
            "width": 64, "words": ["0000000000000001"] * 8,
            "sha256": hashlib.sha256((1).to_bytes(8, "little") * 8).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {}
            for phase in manifest["phases"]:
                source = root / f"{phase['name']}.sv"
                source.write_text(f"module {phase['top']}; endmodule\n")
                phase["namespaced_sv_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
                sources[phase["name"]] = source
            target = root / "package"
            receipt = write_package(manifest, sources, target)
            self.assertEqual(json.loads((target / "receipt.json").read_text()), receipt)
            self.assertEqual(receipt["files"]["phase0_mem31.hex"],
                             hashlib.sha256((target / "phase0_mem31.hex").read_bytes()).hexdigest())
            self.assertEqual(receipt["sources"], [str(sources[name]) for name in manifest["phase_order"]])

    def test_autonomous_three_phase_memory_contract(self):
        if shutil.which("verilator") is None:
            self.skipTest("Verilator unavailable outside Nix")
        manifest = small_manifest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "shell.sv").write_text(render_shell(manifest))
            (root / "phases.sv").write_text("\n".join(
                synthetic_phase(phase, index) for index, phase in enumerate(manifest["phases"])))
            (root / "tb.sv").write_text(synthetic_testbench())
            command = ["verilator", "--binary", "--timing", "--top-module", "tb", "-Wno-fatal",
                       "--Mdir", str(root / "obj"), str(root / "shell.sv"),
                       str(root / "phases.sv"), str(root / "tb.sv")]
            compiled = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
            self.assertEqual(compiled.returncode, 0, compiled.stdout[-3000:] + compiled.stderr[-3000:])
            simulated = subprocess.run([str(root / "obj" / "Vtb")], cwd=root,
                                       capture_output=True, text=True, timeout=30)
            self.assertEqual(simulated.returncode, 0, simulated.stdout + simulated.stderr)
            self.assertIn("PASS rc synthetic 237 words tokens=2,3,4", simulated.stdout)
            if shutil.which("yosys") is not None:
                elaborated = subprocess.run(
                    ["yosys", "-Q", "-T", "-p",
                     f"read_verilog -sv -D SYNTHESIS {root / 'shell.sv'} {root / 'phases.sv'}; "
                     "hierarchy -check -top rc_phase_composed"],
                    cwd=root, capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(elaborated.returncode, 0,
                                 elaborated.stdout[-3000:] + elaborated.stderr[-3000:])


if __name__ == "__main__":
    unittest.main()
