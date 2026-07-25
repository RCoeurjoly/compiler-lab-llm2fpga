{ pkgs
, simulator
}:

pkgs.runCommand "tinystories-w8a8-rc-cached-sv-heartbeat-run" {
  nativeBuildInputs = [ pkgs.coreutils ];
} ''
  mkdir -p "$out"
  set +e
  (cd ${simulator}/verilator-work && \
    timeout --signal=TERM 900 ./obj_dir/Vtb) > "$out/heartbeat.log" 2>&1
  status=$?
  printf '%s\n' "$status" > "$out/exit-status"
  exit 0
''
