#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  echo "usage: tosa_to_linalg.sh <mlir-opt> <mlir-pass-plugin> <input-tosa-mlir> <output-linalg-mlir>" >&2
  echo "or set MLIR_OPT and MLIR_PASS_PLUGIN and call: tosa_to_linalg.sh <input-tosa-mlir> <output-linalg-mlir>" >&2
  exit 1
}

if [ "$#" -eq 4 ]; then
  mlir_opt="$1"
  pass_plugin="$2"
  input="$3"
  output="$4"
elif [ "$#" -eq 2 ]; then
  mlir_opt="${MLIR_OPT:-}"
  pass_plugin="${MLIR_PASS_PLUGIN:-}"
  input="$1"
  output="$2"
  [ -n "$mlir_opt" ] || usage
  [ -n "$pass_plugin" ] || usage
else
  usage
fi

require_executable "$mlir_opt"
require_file "$pass_plugin"
require_file "$input"

validated_tosa="$(mktemp /tmp/llm2fpga_validated_tosa_XXXXXX.mlir)"
trap 'rm -f "$validated_tosa"' EXIT

run_to_output "$validated_tosa" "$mlir_opt" "$input" \
  "--load-pass-plugin=$pass_plugin" \
  '--pass-pipeline=builtin.module(llm2fpga-legalize-pt2e-tosa-zero-point,canonicalize,cse,tosa-validate)'

run_to_output "$output" "$mlir_opt" "$validated_tosa" \
  --tosa-to-linalg-pipeline \
  --tosa-to-tensor \
  --tosa-to-arith='include-apply-rescale' \
  -canonicalize \
  -cse
