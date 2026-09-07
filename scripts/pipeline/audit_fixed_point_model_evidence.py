#!/usr/bin/env python3
"""Audit saved full-model execution and compile same-Futil synthesis evidence.

Never executes the simulator. All synthesis subprocesses share a bounded budget.
Resource numbers are RTLIL hierarchy/stat counts, before proc or technology mapping.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "tinystories-1m-model-same-futil-audit-v1"


def load_runner():
    spec = importlib.util.spec_from_file_location("saved_model_evidence_runner", ROOT / "scripts/pipeline/run_fixed_point_model_sv.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_record(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def boundaries(oracle):
    result = {}
    for step in oracle["steps"]:
        index = step["step_index"]
        for name in ("token", "position", "sum"):
            result[index, "embedding." + name] = step["embedding"][name]
        for block in step["transformer_blocks"]:
            result[index, "block." + str(block["block_index"])] = block["output"]
        result[index, "final_ln"] = step["final_layer_norm"]["output"]
        for name in ("full_context_logits", "last_logits"):
            result[index, "lm_head." + name] = step["lm_head"][name]
    return result


def validate_transcript(events, oracle):
    """Strictly consume both complete runs, including their feedback events."""
    expected = []
    for run in range(2):
        expected.append(dict(event="isolation", run=run, reset=True, idle=True, invalid=True))
        for step in oracle["steps"]:
            index = step["step_index"]
            for (boundary_step, name) in boundaries(oracle):
                if boundary_step == index:
                    expected.append(dict(event="boundary", run=run, step=index, boundary=name, file=f"{run}-{index}-{name}.bin"))
            token = step["selected_token"]["value"]
            expected.append(dict(event="selected", run=run, step=index, token=token, context=step["context_tokens"] + [token]))
        expected.append(dict(event="complete", run=run))
    if len(events) != len(expected):
        raise ValueError(f"transcript_event_count: expected={len(expected)} observed={len(events)}")
    previous = [0, 0]
    normalized = [[], []]
    for index, (event, want) in enumerate(zip(events, expected)):
        stripped = {k: v for k, v in event.items() if k != "cycles"}
        if stripped != want or any(type(event.get(k)) is not type(v) for k, v in want.items()):
            raise ValueError(f"transcript_order_or_fields: event={index} expected={want} observed={event}")
        run = want["run"]
        if event["event"] == "isolation":
            if "cycles" in event:
                raise ValueError("isolation_unexpected_cycles")
        else:
            cycles = event.get("cycles")
            if type(cycles) is not int or not previous[run] <= cycles < 2000000000 or cycles <= 0:
                raise ValueError(f"transcript_cycles: run={run} event={index}")
            if event["event"] in ("selected", "complete") and cycles == previous[run]:
                raise ValueError("transcript_commit_cycle_order")
            previous[run] = cycles
        normalized[run].append({k: v for k, v in event.items() if k not in ("run", "file")})
    if normalized[0] != normalized[1]:
        raise ValueError("restart_transcript_mismatch")
    return {"event_count": len(events), "boundary_count": sum(x["event"] == "boundary" for x in events), "cycles": previous,
            "selected_tokens": [[x["token"] for x in events if x["event"] == "selected" and x["run"] == run] for run in range(2)]}


def verify_snapshot(event, directory, expected):
    import numpy as np
    path = directory / event["file"]
    if path.name != f"{event['run']}-{event['step']}-{event['boundary']}.bin" or path.resolve().parent != directory.resolve():
        raise ValueError("snapshot_path_identity")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    diagnostic = f"run={event['run']} step={event['step']} boundary={event['boundary']}"
    if len(raw) != expected["bytes"] or digest != expected["little_endian_int64_sha256"]:
        raise ValueError(f"first_divergence: {diagnostic} expected={expected['little_endian_int64_sha256']} observed={digest} bytes={len(raw)}")
    semantic = canonical({"shape": expected["shape"], "dtype": expected["dtype"], "values": np.frombuffer(raw, dtype="<i8").reshape(expected["shape"]).tolist()})
    if semantic != expected["sha256"]:
        raise ValueError("semantic_tensor_hash_mismatch: " + diagnostic)
    return {"run": event["run"], "step": event["step"], "boundary": event["boundary"], "cycles": event["cycles"], "shape": expected["shape"], "sha256": semantic, "snapshot": file_record(path)}


def verify_meminit_warnings(warnings, futil):
    names = re.findall(r"@external\s+(\w+)\s*=\s*seq_mem_d1\(", futil)
    expected = ["DATA (path to meminit files): ", *[f"%Warning: /{name}.dat:0: $readmem file not found" for name in names]]
    if not names or warnings != expected:
        raise ValueError("default_meminit_not_proven_absent")


def audit_saved(directory):
    runner = load_runner()
    receipt_path = directory / "execution-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    runner.validate_execution_receipt(receipt, verify_artifacts=True)
    artifact = runner.lowerer.generate_model_kernel()
    oracle = json.loads(runner.lowerer.ORACLE.read_text())
    if receipt["provenance_sha256"] != artifact.provenance["artifact_sha256"]:
        raise ValueError("provenance_authority_mismatch")
    if (directory / "model.futil").read_text() != artifact.futil:
        raise ValueError("saved_futil_authority_mismatch")
    for filename, text in (("harness.cpp", runner.generate_harness(artifact)), ("visibility.vlt", runner.generate_visibility_config(artifact))):
        if (directory / filename).read_text() != text:
            raise ValueError("saved_harness_or_visibility_mismatch: " + filename)
    stages = receipt["stages"]
    if [x["stage"] for x in stages] != ["calyx_resolution", "calyx_simulation", "verilator_build", "generated_sv_execution"]:
        raise ValueError("saved_stage_sequence")
    for stage in stages:
        if file_record(stage["log"]["path"]) != stage["log"] or not 0 < stage["elapsed_seconds"] <= 7200:
            raise ValueError("saved_stage_log_or_time")
    install = Path((directory / "calyx_resolution.log").read_text().strip().splitlines()[-1])
    common = [str(install / "bin/calyx"), str(directory / "model.futil"), "-l", str(install / "share/calyx"), "-d", "cell-share"]
    expected_commands = [
        ["nix", "build", "--no-link", "--print-out-paths", ".#calyx"],
        [*common, "-b", "verilog", "-o", str(directory / "model.sv")],
        ["verilator", "--cc", "--exe", "--build", "-j", "4", "--top-module", "main", "--Mdir", str(directory / "verilator"), "-CFLAGS", "-std=c++17", "-MAKEFLAGS", "OPT_SLOW=-O0", "-o", "model_harness", str(directory / "visibility.vlt"), str(directory / "model.sv"), str(directory / "harness.cpp")],
        [str(directory / "verilator/model_harness"), str(directory)],
    ]
    if [x["command"] for x in stages] != expected_commands:
        raise ValueError("saved_compile_or_execution_command")
    expected_paths = {"futil": "model.futil", "sv": "model.sv", "harness": "harness.cpp", "visibility": "visibility.vlt", "executable": "verilator/model_harness", "execution_log": "generated_sv_execution.log"}
    if receipt["generated_artifacts"] != {k: file_record(directory / v) for k, v in expected_paths.items()}:
        raise ValueError("saved_artifact_path_identity")
    events, warnings = [], []
    for line in (directory / "generated_sv_execution.log").read_text().splitlines():
        if line.startswith("{"):
            events.append(json.loads(line))
        elif line == "DATA (path to meminit files): " or re.fullmatch(r"%Warning: /\w+\.dat:0: \$readmem file not found", line):
            warnings.append(line)
        elif line.strip():
            raise ValueError("unexpected_execution_log_line: " + line)
    verify_meminit_warnings(warnings, artifact.futil)
    transcript = validate_transcript(events, oracle)
    if transcript["cycles"] != receipt["execution"]["cycles"]:
        raise ValueError("receipt_transcript_cycles")
    checkpoints = boundaries(oracle)
    snapshots = [verify_snapshot(event, directory, checkpoints[event["step"], event["boundary"]]) for event in events if event["event"] == "boundary"]
    for run in range(2):
        observed = [{"step": x["step"], "boundary": x["boundary"], "cycles": x["cycles"], "shape": x["shape"], "sha256": x["sha256"], "little_endian_int64_sha256": x["snapshot"]["sha256"]} for x in snapshots if x["run"] == run]
        if observed != receipt["boundaries"]:
            raise ValueError(f"receipt_boundary_transcript: run={run}")
        isolation = next(x for x in events if x["event"] == "isolation" and x["run"] == run)
        if isolation != receipt["reset"]["initial" if run == 0 else "restart"]:
            raise ValueError("receipt_isolation_transcript")
    capture = runner.lowerer._load(ROOT / "TinyStories/capture_fixed_point_model_token_step_oracle.py", "saved_model_audit_oracle")
    bundle = capture.exact_adapter.load_successor_exact_model(capture.DEFAULT_CONTRACT, capture.DEFAULT_PACKAGE, capture.DEFAULT_MODEL, capture.DEFAULT_GENERATION)
    sources = runner.lowerer.materialize_model_sources(artifact, bundle)
    if set(sources) != set(receipt["source_artifacts"]):
        raise ValueError("source_memory_coverage")
    for name, tensor in sources.items():
        raw = tensor.numpy().astype("<i8").tobytes()
        path = directory / ("source-" + name + ".bin")
        if path.read_bytes() != raw or receipt["source_artifacts"][name] != file_record(path):
            raise ValueError("source_authority_mismatch: " + name)
    return {"receipt": file_record(receipt_path), "receipt_sha256": receipt["receipt_sha256"], "oracle_sha256": oracle["artifact_sha256"], "provenance_sha256": artifact.provenance["artifact_sha256"], "futil": file_record(directory / "model.futil"), "simulation_sv": file_record(directory / "model.sv"), "harness": file_record(directory / "harness.cpp"), "source_artifacts": receipt["source_artifacts"], "transcript": transcript, "events": events, "snapshots": snapshots, "simulation_meminit_warnings": warnings, "simulation_timebox": receipt["timebox"], "compiler_common_command": common}


def parse_resources(stats):
    if "\\main" not in stats.get("modules", {}) or "design" not in stats:
        raise ValueError("yosys_missing_hierarchy")
    result = {}
    for key in ("cells", "memories", "memory_bits", "processes"):
        value = stats["design"].get("num_" + key)
        if type(value) is not int or value <= 0:
            raise ValueError("yosys_missing_resource: " + key)
        result[key] = value
    return result


def validate_evidence(evidence, *, verify_artifacts=True):
    """Offline structural checks, plus full saved-file re-audit by default."""
    if evidence.get("artifact_sha256") != canonical({k: v for k, v in evidence.items() if k != "artifact_sha256"}):
        raise ValueError("evidence_self_hash")
    if evidence.get("schema") != SCHEMA or evidence.get("status") != "passed":
        raise ValueError("evidence_not_passed")
    for claim in ("board_fit", "board_execution", "timing_or_place_and_route", "arbitrary_pytorch_graph_lowering"):
        if evidence["claims"].get(claim) is not False:
            raise ValueError("unsupported_claim: " + claim)
    if evidence["claims"].get("same_futil_simulation_and_synthesis") is not True or evidence["claims"].get("saved_snapshot_checks") != 56:
        raise ValueError("evidence_scope")
    if evidence["resources"] != parse_resources({"modules": {"\\main": {}}, "design": evidence["yosys_statistics"]["design"]}):
        raise ValueError("resource_statistics_mismatch")
    saved = evidence["saved_execution"]
    oracle = json.loads((ROOT / "artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json").read_text())
    if validate_transcript(saved["events"], oracle) != saved["transcript"] or saved["oracle_sha256"] != oracle["artifact_sha256"]:
        raise ValueError("evidence_transcript")
    if not 0 < evidence["timebox"]["elapsed_seconds"] <= evidence["timebox"]["timeout_seconds"] <= 7200:
        raise ValueError("evidence_timebox")
    common = saved["compiler_common_command"]
    sv = evidence["synthesis_sv"]["path"]
    stats = evidence["yosys_statistics"]["artifact"]["path"]
    commands = [
        [*common, "-b", "verilog", "-o", evidence["reproduced_simulation_sv"]["path"]],
        [*common, "--synthesis", "--disable-verify", "-b", "verilog", "-o", sv],
        [evidence["tools"]["yosys"]["path"], "-p", f"read_verilog -sv {sv}; hierarchy -check -top main; stat; tee -o {stats} stat -json"],
    ]
    if [x["stage"] for x in evidence["stages"]] != ["simulation_sv_reproduction", "calyx_synthesis", "yosys_hierarchy_stat"] or [x["command"] for x in evidence["stages"]] != commands or any(x["returncode"] != 0 for x in evidence["stages"]):
        raise ValueError("synthesis_stage_contract")
    if evidence["reproduced_simulation_sv"]["sha256"] != saved["simulation_sv"]["sha256"]:
        raise ValueError("simulation_sv_reproduction")
    if verify_artifacts:
        if evidence["verifier"] != file_record(Path(__file__).resolve()):
            raise ValueError("verifier_source_mismatch")
        if audit_saved(Path(saved["receipt"]["path"]).parent) != saved:
            raise ValueError("saved_execution_reaudit_mismatch")
        records = [evidence["synthesis_sv"], evidence["reproduced_simulation_sv"], evidence["yosys_statistics"]["artifact"], *evidence["tools"].values(), *[x["log"] for x in evidence["stages"]]]
        for record in records:
            if file_record(record["path"]) != record:
                raise ValueError("evidence_artifact_mismatch: " + record["path"])
        if json.loads(Path(stats).read_text())["design"] != evidence["yosys_statistics"]["design"]:
            raise ValueError("yosys_json_design_mismatch")
    return evidence


def run(directory, output, timeout):
    if not 0 < timeout <= 7200:
        raise ValueError("timeout must be in (0, 7200]")
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    stages = []

    def stage(name, command):
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("deadline_exceeded: " + name)
        begin = time.monotonic()
        log = output / (name + ".log")
        with log.open("w") as stream:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=remaining, check=False)
            except subprocess.TimeoutExpired as error:
                raise ValueError("deadline_exceeded: " + name) from error
        stages.append({"stage": name, "command": command, "elapsed_seconds": time.monotonic() - begin, "returncode": result.returncode, "log": file_record(log)})
        if result.returncode:
            raise ValueError(f"stage_failed: {name} exit={result.returncode}: {log}")
        return log.read_text()

    current = "saved_execution_audit"
    try:
        saved = audit_saved(directory)
        current = "simulation_sv_reproduction"
        reproduced = output / "model-simulation-reproduced.sv"
        common = saved["compiler_common_command"]
        stage(current, [*common, "-b", "verilog", "-o", str(reproduced)])
        if reproduced.read_bytes() != (directory / "model.sv").read_bytes():
            raise ValueError("simulation_sv_reproduction_mismatch")
        current = "calyx_synthesis"
        sv = output / "model-synthesis.sv"
        stage(current, [*common, "--synthesis", "--disable-verify", "-b", "verilog", "-o", str(sv)])
        current = "yosys_hierarchy_stat"
        yosys = shutil.which("yosys")
        if not yosys:
            raise ValueError("yosys_missing")
        stats_path = output / "stat.json"
        stage(current, [yosys, "-p", f"read_verilog -sv {sv}; hierarchy -check -top main; stat; tee -o {stats_path} stat -json"])
        stats = json.loads(stats_path.read_text())
        resources = parse_resources(stats)
        if saved["futil"] != file_record(directory / "model.futil"):
            raise ValueError("same_futil_changed_during_synthesis")
        evidence = {"schema": SCHEMA, "status": "passed", "saved_execution": saved, "verifier": file_record(Path(__file__).resolve()), "synthesis_sv": file_record(sv), "reproduced_simulation_sv": file_record(reproduced), "tools": {"calyx": file_record(common[0]), "yosys": file_record(yosys)}, "stages": stages, "resources": resources, "timebox": {"timeout_seconds": timeout, "elapsed_seconds": time.monotonic() - started}, "claims": {"same_futil_simulation_and_synthesis": True, "saved_snapshot_checks": 56, "authenticated_source_preloads": True, "resource_scope": "Yosys read_verilog; hierarchy -check -top main; stat; RTLIL before proc, memory mapping, optimization, or technology mapping", "synthesis_assertions": "--disable-verify suppresses simulation guard assertions, matching existing block synthesis policy; no hand-edited RTL", "board_execution": False, "board_fit": False, "timing_or_place_and_route": False, "arbitrary_pytorch_graph_lowering": False, "compiler_scope": "Exact-model generated schedule composes existing fixed-point arithmetic templates"}}
        evidence["yosys_statistics"] = {"artifact": file_record(stats_path), "creator": stats["creator"], "design": stats["design"]}
        evidence["artifact_sha256"] = canonical(evidence)
        validate_evidence(evidence, verify_artifacts=False)
        (output / "evidence.json").write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
        return evidence
    except Exception as error:
        failure = {"status": "failed", "stage": current, "diagnostic": str(error), "stages": stages, "timeout_seconds": timeout, "elapsed_seconds": time.monotonic() - started}
        failure["artifact_sha256"] = canonical(failure)
        (output / "failure.json").write_text(json.dumps(failure, sort_keys=True, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("/tmp/llm2fpga-tinystories-model-bank-local-v1"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/llm2fpga-tinystories-model-synthesis-audit-v1"))
    parser.add_argument("--receipt", type=Path, default=ROOT / "artifacts/reference/tinystories-1m-model-same-futil-evidence.json")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--verify-only", action="store_true", help="recheck receipt and saved files without any synthesis or simulation")
    args = parser.parse_args()
    if args.verify_only:
        evidence = validate_evidence(json.loads(args.receipt.read_text()))
    else:
        evidence = run(args.directory.resolve(), args.output.resolve(), args.timeout)
        args.receipt.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": evidence["status"], "artifact_sha256": evidence["artifact_sha256"], "resources": evidence["resources"], "transcript": evidence["saved_execution"]["transcript"]}))


if __name__ == "__main__":
    main()
