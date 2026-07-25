{ pkgs
, simulator
, timeoutSeconds ? 120
}:

pkgs.runCommand "tinystories-w8a8-rc-cached-sv-heartbeat-run" {
  nativeBuildInputs = [ pkgs.coreutils ];
} ''
  mkdir -p "$out"
  set +e
  start=$(date +%s%N)
  (cd ${simulator}/verilator-work && \
    timeout --signal=TERM ${toString timeoutSeconds} ./obj_dir/Vtb) > "$out/heartbeat.log" 2>&1
  status=$?
  end=$(date +%s%N)
  ${pkgs.python3}/bin/python3 - "$start" "$end" "$status" > "$out/runtime.json" <<'PY'
import json, sys
start, end, status = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
print(json.dumps({"wall_seconds": (end - start) / 1e9, "exit_status": status}, sort_keys=True))
PY
  printf '%s\n' "$status" > "$out/exit-status"
  exit 0
''
