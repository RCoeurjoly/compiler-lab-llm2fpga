#!/usr/bin/env bash
set -euo pipefail

mlir_opt="${1:?usage: scf_to_flat_scf_no_handshake.sh <mlir-opt> <input-scf-mlir> <output-dir>}"
input="${2:?usage: scf_to_flat_scf_no_handshake.sh <mlir-opt> <input-scf-mlir> <output-dir>}"
output_dir="${3:?usage: scf_to_flat_scf_no_handshake.sh <mlir-opt> <input-scf-mlir> <output-dir>}"
blocker_report="${FLAT_SCF_BLOCKER_REPORT:?set FLAT_SCF_BLOCKER_REPORT to flat_scf_blocker_report.py}"

if [[ ! -x "$mlir_opt" ]]; then
  echo "not executable: $mlir_opt" >&2
  exit 2
fi

if [[ ! -f "$input" ]]; then
  echo "missing input MLIR: $input" >&2
  exit 2
fi

tmp_flat="$(mktemp /tmp/no_handshake_flat_scf_XXXXXX.mlir)"
cleanup() {
  rm -f "$tmp_flat"
}
trap cleanup EXIT

mkdir -p "$output_dir"

"$mlir_opt" "$input" \
  --flatten-memref \
  --canonicalize \
  --cse \
  -o "$tmp_flat"

cp "$tmp_flat" "$output_dir/flat.scf.mlir"

python3 "$blocker_report" \
  --input "$output_dir/flat.scf.mlir" \
  --output "$output_dir/blockers.json" \
  --manifest-output "$output_dir/manifest.json"
