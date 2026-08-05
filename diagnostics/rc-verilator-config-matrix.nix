{ pkgs
, sv
, image
, configurations ? [
    # The validated baseline uses coarse C++ partitions and a threaded model.
    # The next two points vary one factor at a time: model threads, then split
    # granularity.  The earlier 100/50 point is intentionally opt-in: it
    # produces tens of thousands of C++ files and is not a practical cold
    # iteration baseline.
    {
      name = "coarse-threaded";
      verilateJobs = 4;
      buildJobs = 4;
      outputSplit = 10000;
      outputSplitCfuncs = 10000;
      threads = 8;
    }
    {
      name = "coarse-single-thread";
      verilateJobs = 4;
      buildJobs = 4;
      outputSplit = 10000;
      outputSplitCfuncs = 10000;
      threads = 1;
    }
    {
      name = "split-500-threaded";
      verilateJobs = 4;
      buildJobs = 4;
      outputSplit = 500;
      outputSplitCfuncs = 250;
      threads = 8;
    }
  ]
, caseId ? "ascending"
, timeoutCycles ? 2000000
, probeSeconds ? 15
, heartbeatCycles ? 1000
}:

pkgs.runCommand "tinystories-w8a8-rc-verilator-config-matrix" {
  nativeBuildInputs = [
    pkgs.python3
    pkgs.bash
    pkgs.verilator
    pkgs.gnumake
    pkgs.stdenv.cc
  ];
} ''
  set -euo pipefail
  mkdir -p "$out"
  ${pkgs.python3}/bin/python3 - \
    "$out" \
    '${builtins.toJSON configurations}' \
    '${caseId}' \
    '${toString timeoutCycles}' \
    '${toString probeSeconds}' \
    '${toString heartbeatCycles}' \
    ${../scripts/pipeline/run_rc_sv_equivalence.py} \
    ${sv}/sv/main.sv \
    ${image}/rc-image.bin \
    ${image}/rc-image-manifest.json \
    ${image}/reference.json \
    ${pkgs.verilator}/bin/verilator <<'PY'
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time

(
    out_text,
    configurations_text,
    case_id,
    timeout_cycles_text,
    probe_seconds_text,
    heartbeat_cycles_text,
    runner_text,
    sv_text,
    image_text,
    manifest_text,
    reference_text,
    verilator_text,
) = sys.argv[1:]
out = pathlib.Path(out_text)
configurations = json.loads(configurations_text)
if not configurations:
    raise SystemExit("configuration matrix must contain a baseline configuration")
timeout_cycles = int(timeout_cycles_text)
probe_seconds = int(probe_seconds_text)
heartbeat_cycles = int(heartbeat_cycles_text)
runner = pathlib.Path(runner_text)
reference = json.loads(pathlib.Path(reference_text).read_text(encoding="utf-8"))
case_index = next(
    (index for index, case in enumerate(reference["results"]) if case["case_id"] == case_id),
    None,
)
if case_index is None:
    raise SystemExit(f"unknown reference case: {case_id}")
expected_result_line = "RESULT " + case_id + " " + " ".join(
    str(value) for value in reference["results"][case_index]["output_codes_i8"]
)


def error_text(process):
    text = process.stderr or ""
    return text[-4000:]


def timeout_output(error):
    output = error.output or ""
    return output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output


results = []
for config in configurations:
    name = config["name"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise SystemExit(f"unsafe matrix configuration name: {name}")
    config_dir = out / "configurations" / name
    work = out / "work" / name
    config_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    compile_json = config_dir / "compile.json"
    compile_command = [
        sys.executable,
        str(runner),
        "--sv", sv_text,
        "--image", image_text,
        "--manifest", manifest_text,
        "--reference", reference_text,
        "--verilator", verilator_text,
        "--verilate-jobs", str(config["verilateJobs"]),
        "--build-jobs", str(config["buildJobs"]),
        "--verilator-output-split", str(config["outputSplit"]),
        "--verilator-output-split-cfuncs", str(config["outputSplitCfuncs"]),
        "--verilator-threads", str(config["threads"]),
        "--heartbeat-cycles", "0",
        "--case-id", case_id,
        "--work-dir", str(work),
        "--timing-json", str(compile_json),
        "--compile-only",
    ]
    compile_process = subprocess.run(
        compile_command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if compile_process.returncode != 0 or not compile_json.exists():
        results.append({
            "name": name,
            "configuration": config,
            "compile": {"status": "failed", "returncode": compile_process.returncode,
                        "stderr": error_text(compile_process)},
            "runtime": {"status": "skipped"},
        })
        shutil.rmtree(work)
        continue
    compile_result = json.loads(compile_json.read_text(encoding="utf-8"))
    binary = work / "obj_dir" / "Vtb"
    runtime_command = [
        str(binary),
        f"+heartbeat_cycles={heartbeat_cycles}",
        f"+timeout_cycles={timeout_cycles}",
        "+stop_after_output=1",
        "+trace_output_writes=0",
        f"+case_index={case_index}",
    ]
    runtime_start = time.perf_counter()
    try:
        runtime_process = subprocess.run(
            runtime_command,
            cwd=work,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=probe_seconds,
            check=False,
        )
        runtime_output = runtime_process.stdout
        runtime_status = "finished" if runtime_process.returncode == 0 else "failed"
        returncode = runtime_process.returncode
    except subprocess.TimeoutExpired as error:
        runtime_output = timeout_output(error)
        runtime_status = "timeout"
        returncode = None
    runtime_seconds = time.perf_counter() - runtime_start
    (config_dir / "runtime.log").write_text(runtime_output, encoding="utf-8")
    heartbeats = [
        int(match.group(1))
        for match in re.finditer(r"HEARTBEAT \S+ cycles=(\d+)", runtime_output)
    ]
    last_heartbeat = max(heartbeats) if heartbeats else None
    result_lines = [
        line for line in runtime_output.splitlines() if line.startswith("RESULT ")
    ]
    testbench_timeout = any(
        line.startswith(f"TIMEOUT {case_id} ")
        for line in runtime_output.splitlines()
    )
    result_validation = "not_reached"
    if result_lines:
        result_validation = (
            "match" if result_lines == [expected_result_line] else "mismatch"
        )
    elif testbench_timeout:
        result_validation = "testbench_timeout"
    if result_validation == "mismatch":
        runtime_status = "mismatch"
    elif runtime_status == "finished":
        if result_validation == "testbench_timeout":
            runtime_status = "testbench_timeout"
        elif result_validation == "not_reached":
            runtime_status = "failed"
    runtime = {
        "status": runtime_status,
        "returncode": returncode,
        "wall_seconds": runtime_seconds,
        "last_heartbeat_cycles": last_heartbeat,
        "cycles_per_second": (last_heartbeat / runtime_seconds)
        if last_heartbeat is not None and runtime_seconds > 0 else None,
        "expected_result_line": expected_result_line,
        "result_lines": result_lines,
        "result_validation": result_validation,
    }
    compile_result.pop("binary", None)
    compile_json.write_text(
        json.dumps(compile_result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    results.append({
        "name": name,
        "configuration": config,
        "compile": compile_result,
        "runtime": runtime,
    })
    shutil.rmtree(work)


def compile_seconds(result):
    return result["compile"].get("timings", {}).get("verilator_compile_seconds", float("inf"))


summary = {
    "purpose": "compile and forward-progress probe; not an equivalence gate",
    "case_id": case_id,
    "probe_seconds": probe_seconds,
    "heartbeat_cycles": heartbeat_cycles,
    "baseline_name": configurations[0]["name"],
    "results": sorted(results, key=compile_seconds),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
lines = ["# RC Verilator configuration matrix", ""]
for result in summary["results"]:
    timing = result["compile"].get("timings", {})
    runtime = result["runtime"]
    lines.append(
        f"- `{result['name']}`: compile={timing.get('verilator_compile_seconds')}, "
        f"codegen={timing.get('verilator_codegen_seconds')}, "
        f"C++={timing.get('cpp_build_seconds')}, "
        f"runtime={runtime['status']}, result={runtime.get('result_validation')}, "
        f"cycles/s={runtime.get('cycles_per_second')}"
    )
(out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
baseline = next(
    (result for result in results if result["name"] == summary["baseline_name"]),
    None,
)
if baseline is None or baseline["compile"].get("status") != "compiled":
    raise SystemExit(f"baseline configuration did not compile: {summary['baseline_name']}")
baseline_runtime = baseline["runtime"]
if (
    baseline_runtime["status"] in {"failed", "mismatch"}
    or (
        not baseline_runtime["result_lines"]
        and baseline_runtime["last_heartbeat_cycles"] is None
    )
):
    raise SystemExit(
        f"baseline configuration did not show runtime progress: {summary['baseline_name']}"
    )
PY
''
