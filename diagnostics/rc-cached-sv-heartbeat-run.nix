{ pkgs
, simulator
}:

pkgs.runCommand "tinystories-w8a8-rc-cached-sv-heartbeat-run" {
  nativeBuildInputs = [ pkgs.coreutils ];
} ''
  set +e
  timeout --signal=TERM 120 ${simulator}/verilator-work/obj_dir/Vtb > "$out/heartbeat.log" 2>&1
  status=$?
  printf '%s\n' "$status" > "$out/exit-status"
  exit 0
''
