#!/usr/bin/env bash
set -euo pipefail

mlir_opt="${1:?usage: linalg_to_llvm_no_handshake.sh <mlir-opt> <input-linalg-mlir> <output-llvm-mlir>}"
input="${2:?usage: linalg_to_llvm_no_handshake.sh <mlir-opt> <input-linalg-mlir> <output-llvm-mlir>}"
output="${3:?usage: linalg_to_llvm_no_handshake.sh <mlir-opt> <input-linalg-mlir> <output-llvm-mlir>}"

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
  --one-shot-bufferize='bufferize-function-boundaries' \
  --convert-bufferization-to-memref \
  --linalg-generalize-named-ops \
  --convert-linalg-to-loops \
  --lower-affine \
  --convert-scf-to-cf \
  --expand-strided-metadata \
  --finalize-memref-to-llvm \
  --convert-index-to-llvm \
  --convert-arith-to-llvm \
  --convert-math-to-llvm \
  --convert-cf-to-llvm \
  --convert-func-to-llvm \
  --reconcile-unrealized-casts \
  -o "$output"
