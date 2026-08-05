{ pkgs
, simulator
, sv
, image
, caseId ? "ascending"
, timeoutCycles ? 2000000
, heartbeatCycles ? 100000
}:

pkgs.runCommand "tinystories-w8a8-rc-first-output-run-${caseId}" {
  nativeBuildInputs = [ pkgs.python3 pkgs.coreutils pkgs.bash ];
} ''
  set -euo pipefail
  work="$out/work"
  mkdir -p "$work/obj_dir"
  ${pkgs.python3}/bin/python3 ${../scripts/pipeline/run_rc_sv_equivalence.py} \
    --sv ${sv}/sv/main.sv \
    --image ${image}/rc-image.bin \
    --manifest ${image}/rc-image-manifest.json \
    --reference ${image}/reference.json \
    --case-id ${caseId} \
    --timeout-cycles ${toString timeoutCycles} \
    --heartbeat-cycles ${toString heartbeatCycles} \
    --stop-after-output \
    --trace-output-writes \
    --work-dir "$work" \
    --fixture-only > "$out/fixture.json"
  cp ${simulator}/simulator "$work/obj_dir/Vtb"
  set +e
  timeout --signal=TERM 600 ${pkgs.python3}/bin/python3 ${../scripts/pipeline/run_rc_sv_equivalence.py} \
    --sv ${sv}/sv/main.sv \
    --image ${image}/rc-image.bin \
    --manifest ${image}/rc-image-manifest.json \
    --reference ${image}/reference.json \
    --case-id ${caseId} \
    --timeout-cycles ${toString timeoutCycles} \
    --heartbeat-cycles ${toString heartbeatCycles} \
    --stop-after-output \
    --trace-output-writes \
    --work-dir "$work" \
    --run-only > "$out/heartbeat.log" 2>&1
  status=$?
  set -e
  ${pkgs.python3}/bin/python3 - "$status" "$out/heartbeat.log" > "$out/summary.json" <<'PY'
import json, re, sys
status, path = int(sys.argv[1]), sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read().splitlines()
heartbeats = []
for line in text:
    m = re.match(r"HEARTBEAT (\S+) cycles=(\d+) state=(\d+) inner_state=(\d+) .*requests=(\d+) mem_completions=(\d+) output_writes=(\d+)", line)
    if m:
        heartbeats.append({"case_id": m.group(1), "cycles": int(m.group(2)), "state": int(m.group(3)), "inner_state": int(m.group(4)), "requests": int(m.group(5)), "memory_completions": int(m.group(6)), "output_writes": int(m.group(7))})
outwrites = [line for line in text if line.startswith("OUTWRITE ")]
results = [line for line in text if line.startswith("RESULT ")]
print(json.dumps({"exit_status": status, "heartbeats": heartbeats, "outwrites": outwrites, "results": results}, sort_keys=True))
PY
  exit 0
''
