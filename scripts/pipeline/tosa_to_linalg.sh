#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

usage() {
  echo "usage: tosa_to_linalg.sh [<mlir-opt>] <input-tosa-mlir> <output-linalg-mlir>" >&2
  echo "or set MLIR_OPT and call: tosa_to_linalg.sh <input-tosa-mlir> <output-linalg-mlir>" >&2
  exit 1
}

if [ "$#" -eq 3 ]; then
  mlir_opt="$1"
  input="$2"
  output="$3"
elif [ "$#" -eq 2 ]; then
  mlir_opt="${MLIR_OPT:-}"
  input="$1"
  output="$2"
  [ -n "$mlir_opt" ] || usage
else
  usage
fi

require_executable "$mlir_opt"
require_file "$input"

run_to_output "$output" "$mlir_opt" "$input" \
  --tosa-to-linalg-pipeline \
  --tosa-to-tensor \
  --tosa-to-arith='include-apply-rescale' \
  -canonicalize \
  -cse
