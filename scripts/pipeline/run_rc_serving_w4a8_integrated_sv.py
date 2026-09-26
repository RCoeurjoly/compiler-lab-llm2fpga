#!/usr/bin/env python3
"""Run the compiler-generated integrated RC shell against its frozen oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import shutil
import signal
import struct
import subprocess
import time
from pathlib import Path

from scripts.pipeline.run_rc_serving_w4a8_sv import normalize_simulation_sv


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_process_result(stage: str, *, timed_out: bool, returncode: int | None) -> str:
    """Keep tool resource failures separate from behavioral mismatches."""
    if timed_out:
        return f"{stage}_timeout"
    if returncode in (-9, 137):
        return f"{stage}_signal9"
    if returncode != 0:
        return f"{stage}_failure"
    return "pass"


def compare_composed_readback(
    manifest: dict, observation: dict, actual: dict[int, int], tokens: list[int]
) -> dict:
    """Compare every raw 64-bit readback word against the frozen RC oracle."""
    expected: dict[int, tuple[int, str, int, int]] = {}
    expected_tokens = []
    for phase_manifest, phase_observation in zip(manifest["phases"], observation["phases"], strict=True):
        name = phase_manifest["name"]
        if phase_observation["name"] != name:
            raise ValueError("observation phase order differs from compiler manifest")
        token = int(phase_observation["token"])
        expected_tokens.append(token)
        expected[phase_manifest["token_address"]] = (token, name, -1, 0)
        logits = phase_manifest["logits"]
        if len(phase_observation["logits"]) != logits["words"]:
            raise ValueError(f"{name}: logits width differs from manifest")
        for index, value in enumerate(phase_observation["logits"]):
            bits = int.from_bytes(struct.pack("<f", float(value)), "little")
            expected[phase_manifest["token_address"] + 1 + index] = (
                bits, name, logits["port"], logits["offset"] + index
            )
        for leaf in phase_manifest["cache_outputs"]:
            payload = bytes.fromhex(phase_observation["cache_leaves"][leaf["leaf"]]["little_endian_hex"])
            if len(payload) != 4 * leaf["words"]:
                raise ValueError(f"{name}: cache leaf {leaf['leaf']} byte count differs")
            for index in range(leaf["words"]):
                bits = int.from_bytes(payload[index * 4:index * 4 + 4], "little")
                expected[leaf["readback_address"] + index] = (bits, name, leaf["port"], index)
    if sorted(expected) != list(range(manifest["readback_words"])):
        raise ValueError("compiler manifest readback addresses are incomplete or overlapping")
    mismatches = []
    for address in sorted(expected):
        value, phase, port, word = expected[address]
        observed = actual.get(address)
        if observed != value:
            xor = None if observed is None else value ^ observed
            mismatches.append({
                "address": address, "phase": phase, "port": port, "word": word,
                "expected": f"0x{value:08x}",
                "actual": None if observed is None else f"0x{observed:08x}",
                "first_differing_bit": None if xor is None else (xor & -xor).bit_length() - 1,
            })
    token_match = tokens == expected_tokens
    return {
        "status": "pass" if not mismatches and token_match and len(actual) == len(expected) else "mismatch",
        "expected_tokens": expected_tokens, "actual_tokens": tokens,
        "readback_word_count": len(expected), "actual_readback_word_count": len(actual),
        "mismatch_count": len(mismatches), "first_mismatch": mismatches[0] if mismatches else None,
    }


def _sv_tb_composed(
    prompt: list[int], address_count: int, timeout_cycles: int, *, handoff_manifest: dict
) -> str:
    prompt_lines = []
    for index, token in enumerate(prompt):
        prompt_lines += [
            "    @(negedge clk);",
            f"    prompt_index = 3'd{index}; prompt_data = 64'd{token}; prompt_write = 1;",
            "    @(negedge clk); prompt_write = 0;",
        ]
    handoff_checks = []
    checked_words = 0
    for index, handoff in enumerate(handoff_manifest["handoffs"]):
        source, destination = index, index + 1
        state = 4 if index == 0 else 7
        handoff_checks += [
            f"logic handoff{index}_checked = 0;",
            "always @(negedge clk) begin",
            f"  if (!reset && dut.state == 4'd{state} && !handoff{index}_checked) begin",
            f"    if (dut.mem_p{destination}_{handoff['token_destination_port']}[0] !== token{source}) "
            f"$fatal(1, \"TOKEN_HANDOFF {index}\");",
        ]
        for leaf in handoff["cache"]:
            for word in range(leaf["words"]):
                checked_words += 1
                handoff_checks.append(
                    f"    if (dut.mem_p{destination}_{leaf['destination_port']}[{word}] !== "
                    f"dut.mem_p{source}_{leaf['source_port']}[{word}]) "
                    f"$fatal(1, \"CACHE_HANDOFF phase={index} port={leaf['destination_port']} word={word}\");"
                )
        handoff_checks += [f"    handoff{index}_checked = 1;", "  end", "end"]
    return "\n".join([
        "`timescale 1ns/1ps",
        "module tb;",
        "logic clk=0, reset=1, prompt_write=0, start=0;",
        "logic [2:0] prompt_index=0; logic [63:0] prompt_data=0;",
        "logic [7:0] readback_addr=0; wire [63:0] readback_data;",
        "wire busy, done, error; wire [63:0] token0, token1, token2;",
        "integer cycles=0, address, fd;",
        "always #5 clk = ~clk;",
        "always @(posedge clk) if (!reset) cycles = cycles + 1;",
        "rc_phase_composed dut(.*);",
        *handoff_checks,
        "initial begin",
        "  repeat (3) @(posedge clk); @(negedge clk); reset=0;",
        *prompt_lines,
        "  @(negedge clk); start=1; @(negedge clk); start=0;",
        f"  while (!done && cycles < {timeout_cycles}) @(negedge clk);",
        "  if (!done) $fatal(1, \"TIMEOUT cycles=%0d\", cycles);",
        "  if (error) $fatal(1, \"PROTOCOL_ERROR\");",
        "  if (!handoff0_checked || !handoff1_checked) $fatal(1, \"HANDOFF_NOT_OBSERVED\");",
        f"  $display(\"HANDOFF_CHECKED {checked_words}\");",
        "  $display(\"TOKENS %0d %0d %0d CYCLES %0d\", token0, token1, token2, cycles);",
        "  fd=$fopen(\"readback.hex\", \"w\");",
        f"  for (address=0; address<{address_count}; address=address+1) begin",
        "    readback_addr=address[7:0]; #1;",
        "    $fwrite(fd, \"%0d %016h\\n\", address, readback_data);",
        "  end",
        "  $fclose(fd); $finish;",
        "end",
        "endmodule", "",
    ])


def _memory_limit(limit_gib: int) -> None:
    limit = limit_gib * 1024**3
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run_bounded_command(
    command: list[str], *, cwd: Path, log: object, timeout_seconds: float, max_memory_gib: int
) -> tuple[bool, int | None]:
    """Timebox a compiler and its worker processes as one process group."""
    process = subprocess.Popen(
        command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True, preexec_fn=lambda: _memory_limit(max_memory_gib),
    )
    try:
        return False, process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        return True, None


def normalize_composed_sources(source_paths: list[Path], work_dir: Path) -> list[Path]:
    """Apply the proven simulation-only frontend repair after source hashing."""
    work_dir.mkdir(parents=True, exist_ok=True)
    normalized_paths = []
    for index, path in enumerate(source_paths):
        normalized = work_dir / f"phase{index}.simulation.sv"
        normalized.write_text(normalize_simulation_sv(path.read_text()))
        normalized_paths.append(normalized)
    return normalized_paths


def run_composed(
    shell: Path, manifest_path: Path, observation_path: Path, work_dir: Path, *,
    verilator: str = "verilator", jobs: int = 1, timeout_cycles: int = 100_000_000,
    compile_timeout_seconds: float = 900, simulation_timeout_seconds: float = 900,
    max_memory_gib: int = 20,
) -> dict:
    """Run the real composed compiler phases with durable failure receipts."""
    if jobs < 1 or compile_timeout_seconds <= 0 or simulation_timeout_seconds <= 0 or max_memory_gib < 1:
        raise ValueError("jobs, timeouts and memory limit must be positive")
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text())
    observation = json.loads(observation_path.read_text())
    receipt_path = shell / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    manifest_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    if receipt["manifest_sha256"] != manifest_hash:
        raise ValueError("composed shell receipt has a different handoff manifest")
    for name, expected_hash in receipt["files"].items():
        path = Path(name)
        if not path.is_absolute():
            path = shell / path
        if not path.is_file() or _sha256(path) != expected_hash:
            raise ValueError(f"composed shell file hash mismatch: {name}")
    source_paths = [Path(path) for path in receipt["sources"]]
    (work_dir / "tb.sv").write_text(_sv_tb_composed(
        [0, 1, 2, 3, 4, 5, 0, 1], manifest["readback_words"], timeout_cycles,
        handoff_manifest=manifest,
    ))
    for image in shell.glob("phase*_mem*.hex"):
        shutil.copyfile(image, work_dir / image.name)
    report = {
        "schema": "rc-phase-composed-sv-equivalence-v1",
        "status": "not-run",
        "manifest_sha256": _sha256(manifest_path),
        "observation_sha256": _sha256(observation_path),
        "package_receipt_sha256": _sha256(receipt_path),
        "shell_sha256": _sha256(shell / "rc_phase_composed.sv"),
        "sources": [{"path": str(path), "sha256": _sha256(path)} for path in source_paths],
        "compile_seconds": None, "simulation_seconds": None,
        "max_memory_gib": max_memory_gib,
    }
    normalize_started = time.monotonic()
    simulation_sources = normalize_composed_sources(source_paths, work_dir)
    report["normalization_seconds"] = time.monotonic() - normalize_started
    report["simulation_sources"] = [
        {"path": str(path), "sha256": _sha256(path)} for path in simulation_sources
    ]

    def save() -> dict:
        (work_dir / "report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        return report

    command = [verilator, "--binary", "--timing", "-Wno-fatal", "--top-module", "tb",
               "--Mdir", str(work_dir / "obj_dir"), "--output-split", "10000",
               "--output-split-cfuncs", "10000", "-j", str(jobs), "-CFLAGS", "-O2",
               str(shell / "rc_phase_composed.sv"), *(str(path) for path in simulation_sources),
               str(work_dir / "tb.sv")]
    report["compile_command"] = command
    started = time.monotonic()
    with (work_dir / "verilator-build.log").open("w") as log:
        timed_out, returncode = run_bounded_command(
            command, cwd=work_dir, log=log, timeout_seconds=compile_timeout_seconds,
            max_memory_gib=max_memory_gib,
        )
    report["compile_seconds"] = time.monotonic() - started
    report["status"] = classify_process_result("compile", timed_out=timed_out, returncode=returncode)
    report["compile_returncode"] = returncode
    if report["status"] != "pass":
        return save()

    started = time.monotonic()
    with (work_dir / "simulation.log").open("w") as log:
        timed_out, returncode = run_bounded_command(
            [str(work_dir / "obj_dir" / "Vtb")], cwd=work_dir, log=log,
            timeout_seconds=simulation_timeout_seconds, max_memory_gib=max_memory_gib,
        )
    report["simulation_seconds"] = time.monotonic() - started
    report["status"] = classify_process_result("simulation", timed_out=timed_out, returncode=returncode)
    report["simulation_returncode"] = returncode
    if report["status"] != "pass":
        return save()

    actual: dict[int, int] = {}
    for line in (work_dir / "readback.hex").read_text().splitlines():
        address_text, value_text = line.split()
        address = int(address_text)
        if address in actual:
            raise ValueError(f"duplicate readback address {address}")
        actual[address] = int(value_text, 16)
    simulation_text = (work_dir / "simulation.log").read_text()
    token_match = re.search(r"TOKENS\s+(\d+)\s+(\d+)\s+(\d+)", simulation_text)
    tokens = [int(value) for value in token_match.groups()] if token_match else []
    report.update(compare_composed_readback(manifest, observation, actual, tokens))
    handoff_match = re.search(r"HANDOFF_CHECKED\s+(\d+)", simulation_text)
    expected_handoff_words = sum(
        leaf["words"] for handoff in manifest["handoffs"] for leaf in handoff["cache"]
    )
    report["handoff_checked_words"] = int(handoff_match.group(1)) if handoff_match else 0
    if report["handoff_checked_words"] != expected_handoff_words:
        report["status"] = "handoff_incomplete"
    return save()


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
    parser.add_argument("--composed", action="store_true",
                        help="run the autonomous three-phase compiler shell")
    parser.add_argument("--max-memory-gib", type=int, default=20)
    args = parser.parse_args()
    if args.composed:
        report = run_composed(
            args.shell, args.manifest, args.observation, args.work_dir,
            verilator=args.verilator, jobs=args.jobs, timeout_cycles=args.timeout_cycles,
            compile_timeout_seconds=args.compile_timeout_seconds,
            simulation_timeout_seconds=args.simulation_timeout_seconds,
            max_memory_gib=args.max_memory_gib,
        )
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "pass" else 1
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
