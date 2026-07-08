#!/usr/bin/env bash
set -euo pipefail

mlir_opt="${1:?usage: linalg_to_scf_no_handshake.sh <mlir-opt> <input-linalg-mlir> <output-scf-mlir>}"
input="${2:?usage: linalg_to_scf_no_handshake.sh <mlir-opt> <input-linalg-mlir> <output-scf-mlir>}"
output="${3:?usage: linalg_to_scf_no_handshake.sh <mlir-opt> <input-linalg-mlir> <output-scf-mlir>}"

if [[ ! -x "$mlir_opt" ]]; then
  echo "not executable: $mlir_opt" >&2
  exit 2
fi

if [[ ! -f "$input" ]]; then
  echo "missing input MLIR: $input" >&2
  exit 2
fi

"$mlir_opt" "$input" \
  --empty-tensor-to-alloc-tensor \
  --one-shot-bufferize='bufferize-function-boundaries function-boundary-type-conversion=identity-layout-map' \
  --convert-bufferization-to-memref \
  --linalg-generalize-named-ops \
  --convert-linalg-to-loops \
  --arith-expand \
  --buffer-results-to-out-params \
  --canonicalize \
  --cse \
  -o "$output"
