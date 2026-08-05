{ pkgs
, sv
, image
, caseId ? "ascending"
, timeoutCycles ? 2000000
, heartbeatCycles ? 100000
, verilatorJobs ? 4
, verilatorThreads ? 8
}:

pkgs.runCommand "tinystories-w8a8-rc-first-output-v5-${caseId}" {
  nativeBuildInputs = [
    pkgs.python3
    pkgs.bash
    pkgs.verilator
    pkgs.gnumake
    pkgs.stdenv.cc
    pkgs.coreutils
  ];
} ''
  set -euo pipefail
  work="$TMPDIR/verilator-work"
  mkdir -p "$work"
  start=$(date +%s%N)
  set +e
  ${pkgs.python3}/bin/python3 ${../scripts/pipeline/run_rc_sv_equivalence.py} \
    --sv ${sv}/sv/main.sv \
    --image ${image}/rc-image.bin \
    --manifest ${image}/rc-image-manifest.json \
    --reference ${image}/reference.json \
    --verilator ${pkgs.verilator}/bin/verilator \
    --verilator-output-split 10000 \
    --verilator-output-split-cfuncs 10000 \
    --verilator-jobs ${toString verilatorJobs} \
    --verilator-threads ${toString verilatorThreads} \
    --timeout-cycles ${toString timeoutCycles} \
    --heartbeat-cycles ${toString heartbeatCycles} \
    --case-id ${caseId} \
    --stop-after-output \
    --trace-output-writes \
    --work-dir "$work" \
    --result-json "$work/result.json" > "$work/heartbeat.log" 2>&1
  sim_status=$?
  set -e
  end=$(date +%s%N)
  mkdir -p "$out"
  test -e "$work/tb.sv" && cp "$work/tb.sv" "$out/tb.sv" || true
  test -e "$work/result.json" && cp "$work/result.json" "$out/result.json" || true
  test -e "$work/obj_dir/Vtb" && cp "$work/obj_dir/Vtb" "$out/simulator" || true
  test -e "$work/heartbeat.log" && cp "$work/heartbeat.log" "$out/heartbeat.log" || true
  ${pkgs.python3}/bin/python3 - "$start" "$end" "$sim_status" > "$out/runtime.json" <<'PY'
import json, sys
start, end, status = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
print(json.dumps({"case_id": "${caseId}", "wall_seconds": (end-start)/1e9,
                  "exit_status": status}, sort_keys=True))
PY
  exit 0
''
