#!/usr/bin/env python3
"""Run the compiler-generated integrated RC shell against its frozen oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sv_tb(prompt: list[int], address_count: int, timeout_cycles: int) -> str:
    prompt_lines = []
    for index, token in enumerate(prompt):
        prompt_lines.extend([
            "    @(negedge clk);",
            f"    prompt_index = 3'd{index}; prompt_data = 64'd{token}; prompt_write = 1'b1;",
            "    @(negedge clk); prompt_write = 1'b0;",
        ])
    return "\n".join([
        "`timescale 1ns/1ps",
        "module tb;",
        "  logic clk = 0, reset = 1;",
        "  logic [2:0] prompt_index = '0; logic [63:0] prompt_data = '0;",
        "  logic prompt_write = 0, go = 0;",
        "  wire busy, done, protocol_error;",
        "  wire [63:0] token0, token1, token2;",
        f"  logic [7:0] readback_address = '0; logic readback_request = 0;",
        "  wire readback_response_valid; wire [63:0] readback_response_data;",
        "  integer cycles = 0; integer address; integer fd;",
        "  always #5 clk = ~clk;",
        "  rc_serving_w4a8_integrated_reference dut(.*);",
        "  always @(posedge clk) if (!reset) cycles = cycles + 1;",
        "  initial begin",
        "    repeat (3) @(posedge clk); @(negedge clk); reset = 1'b0;",
        *prompt_lines,
        "    @(negedge clk); go = 1'b1;",
        "    @(negedge clk); go = 1'b0;",
        f"    while (!done && cycles < {timeout_cycles}) @(posedge clk);",
        "    if (!done) $fatal(1, \"TIMEOUT cycles=%0d\", cycles);",
        "    if (protocol_error) $fatal(1, \"PROTOCOL_ERROR\");",
        "    $display(\"TOKENS %0d %0d %0d CYCLES %0d\", token0, token1, token2, cycles);",
        "    fd = $fopen(\"readback.hex\", \"w\");",
        f"    for (address = 0; address < {address_count}; address = address + 1) begin",
        "      @(negedge clk); readback_address = address[7:0]; readback_request = 1'b1;",
        "      @(posedge clk); #1;",
        "      if (!readback_response_valid) $fatal(1, \"READBACK_NO_RESPONSE address=%0d\", address);",
        "      $fwrite(fd, \"%0d %016h\\n\", address, readback_response_data);",
        "      @(negedge clk); readback_request = 1'b0;",
        "    end",
        "    $fclose(fd); $finish;",
        "  end",
        "endmodule",
        "",
    ])


def _expected_readback(manifest: dict, observation: dict) -> dict[int, int]:
    expected: dict[int, int] = {}
    phases = observation["phases"]
    for word in manifest["words"]:
        phase = phases[{"prefill-8": 0, "decode-8": 1, "decode-9": 2}[word["phase"]]]
        kind = word["kind"]
        index = int(word["flat_index"])
        if kind == "token":
            value = int(phase["greedy_token_id"])
        elif kind == "logits":
            payload = bytes.fromhex(phase["last_logits"]["little_endian_hex"])
            value = int.from_bytes(payload[index * 4:index * 4 + 4], "little")
        elif kind == "cache":
            payload = bytes.fromhex(phase["cache_leaves"][word["leaf"]]["little_endian_hex"])
            value = int.from_bytes(payload[index * 4:index * 4 + 4], "little")
        else:
            raise ValueError(f"unsupported readback kind: {kind}")
        expected[int(word["address"])] = value
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout-cycles", type=int, default=100_000_000)
    parser.add_argument("--compile-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--simulation-timeout-seconds", type=float, default=300.0)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    observation = json.loads(args.observation.read_text(encoding="utf-8"))
    prompt = [0, 1, 2, 3, 4, 5, 0, 1]
    tb = args.work_dir / "tb.sv"
    tb.write_text(_sv_tb(prompt, int(manifest["address_count"]), args.timeout_cycles))
    sources = args.shell / "sources.f"
    command = [
        args.verilator, "--binary", "--timing", "-Wno-fatal",
        "--top-module", "tb", "--Mdir", str(args.work_dir / "obj_dir"),
        "--output-split", "10000", "--output-split-cfuncs", "10000",
        "-j", str(args.jobs), "--threads", str(args.jobs),
        str(args.shell / "generated.sv"), str(args.shell / "reference-top.sv"), str(tb),
    ]
    compile_log = args.work_dir / "verilator-build.log"
    started = time.monotonic()
    with compile_log.open("w", encoding="utf-8") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                timeout=args.compile_timeout_seconds)
    compile_seconds = time.monotonic() - started
    if result.returncode:
        raise RuntimeError(f"Verilator compilation failed; see {compile_log}")
    sim_log = args.work_dir / "simulation.log"
    started = time.monotonic()
    with sim_log.open("w", encoding="utf-8") as log:
        result = subprocess.run([str(args.work_dir / "obj_dir/Vtb")], cwd=args.work_dir,
                                stdout=log, stderr=subprocess.STDOUT,
                                timeout=args.simulation_timeout_seconds)
    simulation_seconds = time.monotonic() - started
    if result.returncode:
        raise RuntimeError(f"integrated simulation failed; see {sim_log}")
    expected = _expected_readback(manifest, observation)
    actual: dict[int, int] = {}
    for line in (args.work_dir / "readback.hex").read_text().splitlines():
        address, value = line.split()
        actual[int(address)] = int(value, 16)
    mismatches = [
        {"address": address, "expected": expected[address], "actual": actual.get(address)}
        for address in sorted(expected) if actual.get(address) != expected[address]
    ]
    sim_text = sim_log.read_text(encoding="utf-8")
    token_match = re.search(r"TOKENS\s+(\d+)\s+(\d+)\s+(\d+)", sim_text)
    expected_tokens = [int(phase["greedy_token_id"]) for phase in observation["phases"]]
    actual_tokens = [int(value) for value in token_match.groups()] if token_match else []
    report = {
        "schema": "rc-serving-w4a8-integrated-sv-equivalence-v1",
        "status": "pass" if not mismatches and actual_tokens == expected_tokens else "mismatch",
        "expected_tokens": expected_tokens, "actual_tokens": actual_tokens,
        "readback_word_count": len(expected), "mismatch_count": len(mismatches),
        "first_mismatch": mismatches[0] if mismatches else None,
        "compile_seconds": compile_seconds, "simulation_seconds": simulation_seconds,
        "shell": str(args.shell), "shell_sha256": _sha256(args.shell / "receipt.json"),
    }
    report_path = args.work_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
