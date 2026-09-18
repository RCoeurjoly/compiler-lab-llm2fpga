#!/usr/bin/env bash
# Run inside nix develop .#default. Vendor sources remain external, read-only inputs.
set -euo pipefail
phase= work_dir= source_dir= parameters= negative= max_cycles=1000000000
simulator=iverilog xsim_bin=
while (($#)); do
  if (($# < 2)); then echo "missing option value: $1" >&2; exit 2; fi
  case "$1" in
    --phase) phase=$2 ;;
    --work-dir) work_dir=$2 ;;
    --uberddr3-source) source_dir=$2 ;;
    --vendor-parameters) parameters=$2 ;;
    --negative-control) negative=$2 ;;
    --max-cycles) max_cycles=$2 ;;
    --simulator) simulator=$2 ;;
    --xsim-bin) xsim_bin=$2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift 2
done
[[ $phase == profile || $phase == startup ]] || { echo "phase not implemented: $phase" >&2; exit 2; }
[[ $simulator == iverilog || $simulator == xsim ]] || { echo "unknown simulator" >&2; exit 2; }
if [[ $simulator == xsim ]]; then
  for tool in xvlog xelab xsim; do
    [[ -n $xsim_bin && -x $xsim_bin/$tool ]] || {
      echo "missing XSim tool: $tool (provide --xsim-bin)" >&2; exit 2;
    }
  done
  xsim_bin=$(realpath "$xsim_bin")
fi
[[ $max_cycles =~ ^[1-9][0-9]*$ ]] || { echo "invalid max cycles" >&2; exit 2; }
[[ -f $parameters ]] || { echo "missing vendor parameters: $parameters" >&2; exit 2; }
[[ $(basename "$parameters") == 4096Mb_ddr3_parameters.vh ]] || {
  echo "expected authentic 4096Mb_ddr3_parameters.vh" >&2; exit 2;
}
[[ -n $source_dir && -f $source_dir/testbench/ddr3.sv ]] || {
  echo "missing UberDDR3 Micron source" >&2; exit 2;
}
[[ -n $work_dir ]] || { echo "--work-dir is required" >&2; exit 2; }
mkdir -p "$work_dir"
work_dir=$(realpath "$work_dir")
source_dir=$(realpath "$source_dir")
parameters=$(realpath "$parameters")
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
extra=()
case "$negative" in
  '') ;;
  wrong-geometry) extra+=(-DMICRON_PROFILE_WRONG_GEOMETRY) ;;
  shortened-startup) extra+=(-DMICRON_NEGATIVE_SHORTENED_STARTUP) ;;
  model-timing) extra+=(-DMICRON_NEGATIVE_MODEL_TIMING) ;;
  *) echo "unknown negative control: $negative" >&2; exit 2 ;;
esac
backing=$(mktemp -d "$work_dir/model-data.XXXXXX")
top=micron_profile_tb
sources=("$repo/sim/compiler_ddr3/micron_profile_tb.sv" "$source_dir/testbench/ddr3.sv")
if [[ $phase == startup ]]; then
  top=startup_tb
  # Upstream RTL sets default_nettype none; analyze legacy primitive models
  # first so that directive does not leak into their implicit input net types.
  sources=("$source_dir"/testbench/models/*_model.v
    "$repo/sim/compiler_ddr3/startup_tb.sv"
    "$repo/sim/compiler_ddr3/uberddr3_micron_memory.sv"
    "$source_dir/testbench/ddr3.sv" "$source_dir/rtl/ddr3_top.v"
    "$source_dir/rtl/ddr3_controller.v" "$source_dir/rtl/ddr3_phy.v")
  extra+=(-DSIM_MODEL -DNO_TEST_MODEL)
fi
sha256sum "$source_dir/testbench/ddr3.sv" "$parameters" \
  "$repo/sim/compiler_ddr3/sim_defines.vh" \
  "${sources[@]}" > "$work_dir/sources.sha256"
cd "$work_dir"
if [[ $simulator == iverilog ]]; then
  timeout --kill-after=10s 120 iverilog -g2012 -s "$top" \
  -I "$repo/sim/compiler_ddr3" -I "$(dirname "$parameters")" \
  "${extra[@]}" -o "$work_dir/profile.vvp" \
  "${sources[@]}" \
  > "$work_dir/compile.log" 2>&1 || { cat "$work_dir/compile.log" >&2; exit 1; }
  run=(vvp -i -n "$work_dir/profile.vvp" "+model_data+$backing" "+max_cycles=$max_cycles")
else
  defines=()
  for define in "${extra[@]}"; do defines+=(-d "${define#-D}"); done
  timeout --kill-after=10s 120 "$xsim_bin/xvlog" --sv "${defines[@]}" \
    -i "$repo/sim/compiler_ddr3" -i "$(dirname "$parameters")" "${sources[@]}" \
    > "$work_dir/compile.log" 2>&1 || { cat "$work_dir/compile.log" >&2; exit 1; }
  timeout --kill-after=10s 1800 "$xsim_bin/xelab" "work.$top" -s micron_snapshot --mt 2 \
    > "$work_dir/elaborate.log" 2>&1 || { cat "$work_dir/elaborate.log" >&2; exit 1; }
  run=("$xsim_bin/xsim" micron_snapshot --R --onerror quit --onfinish quit
    --testplusarg "model_data+$backing" --testplusarg "max_cycles=$max_cycles")
fi
set +e
timeout --kill-after=10s 1800 "${run[@]}" \
  2>&1 | tee "$work_dir/run.log"
run_status=${PIPESTATUS[0]}
set -e
if grep -Eq 'ERROR:|FAIL:|FATAL:|does not match' "$work_dir/run.log"; then
  echo "Micron/model diagnostic rejected" >&2
  exit 1
fi
((run_status == 0)) || exit "$run_status"
marker='PASS: micron profile'
[[ $phase != startup ]] || marker='PASS: startup calibration and BIST'
grep -Fq "$marker" "$work_dir/run.log" || {
  echo "missing terminal acceptance marker" >&2; exit 1;
}
