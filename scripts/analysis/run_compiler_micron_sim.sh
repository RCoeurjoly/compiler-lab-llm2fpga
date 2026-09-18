#!/usr/bin/env bash
# Run inside nix develop .#default. Vendor sources remain external, read-only inputs.
set -euo pipefail
phase= work_dir= source_dir= parameters= negative=
while (($#)); do
  if (($# < 2)); then echo "missing option value: $1" >&2; exit 2; fi
  case "$1" in
    --phase) phase=$2 ;;
    --work-dir) work_dir=$2 ;;
    --uberddr3-source) source_dir=$2 ;;
    --vendor-parameters) parameters=$2 ;;
    --negative-control) negative=$2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift 2
done
[[ $phase == profile ]] || { echo "phase not implemented: $phase" >&2; exit 2; }
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
  *) echo "unknown negative control: $negative" >&2; exit 2 ;;
esac
backing=$(mktemp -d "$work_dir/model-data.XXXXXX")
sha256sum "$source_dir/testbench/ddr3.sv" "$parameters" \
  "$repo/sim/compiler_ddr3/sim_defines.vh" \
  "$repo/sim/compiler_ddr3/micron_profile_tb.sv" > "$work_dir/sources.sha256"
timeout --kill-after=10s 120 iverilog -g2012 -s micron_profile_tb \
  -I "$repo/sim/compiler_ddr3" -I "$(dirname "$parameters")" \
  "${extra[@]}" -o "$work_dir/profile.vvp" \
  "$repo/sim/compiler_ddr3/micron_profile_tb.sv" "$source_dir/testbench/ddr3.sv" \
  > "$work_dir/compile.log" 2>&1 || { cat "$work_dir/compile.log" >&2; exit 1; }
timeout --kill-after=10s 120 vvp -n "$work_dir/profile.vvp" "+model_data+$backing" \
  | tee "$work_dir/run.log"
