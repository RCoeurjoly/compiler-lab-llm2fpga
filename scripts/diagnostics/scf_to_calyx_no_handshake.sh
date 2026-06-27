#!/usr/bin/env bash
set -euo pipefail

circt_opt="${1:?usage: scf_to_calyx_no_handshake.sh <circt-opt> <input-scf-mlir> <output-dir>}"
input="${2:?usage: scf_to_calyx_no_handshake.sh <circt-opt> <input-scf-mlir> <output-dir>}"
output_dir="${3:?usage: scf_to_calyx_no_handshake.sh <circt-opt> <input-scf-mlir> <output-dir>}"

if [[ ! -x "$circt_opt" ]]; then
  echo "not executable: $circt_opt" >&2
  exit 2
fi

if [[ ! -f "$input" ]]; then
  echo "missing input MLIR: $input" >&2
  exit 2
fi

tmp_flat="$(mktemp /tmp/no_handshake_flat_XXXXXX.mlir)"
tmp_log="$(mktemp /tmp/no_handshake_calyx_XXXXXX.log)"
cleanup() {
  rm -f "$tmp_flat" "$tmp_log"
}
trap cleanup EXIT

mkdir -p "$output_dir"

"$circt_opt" "$input" \
  --flatten-memref \
  --canonicalize \
  --cse \
  -o "$tmp_flat"

cp "$tmp_flat" "$output_dir/flat.scf.mlir"

set +e
"$circt_opt" "$tmp_flat" \
  --lower-scf-to-calyx='top-level-function=main' \
  -o "$output_dir/model.calyx.mlir" >"$tmp_log" 2>&1
rc=$?
set -e

cp "$tmp_log" "$output_dir/lower-scf-to-calyx.log"

if [[ "$rc" -eq 0 && -s "$output_dir/model.calyx.mlir" ]]; then
  cat >"$output_dir/manifest.json" <<'JSON'
{"stage":"calyx","status":"ok","artifact":"model.calyx.mlir"}
JSON
  exit 0
fi

rm -f "$output_dir/model.calyx.mlir"
python3 - "$output_dir/manifest.json" "$rc" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "stage": "calyx",
            "status": "failed",
            "exit_code": int(sys.argv[2]),
            "reason": "lower-scf-to-calyx did not produce a Calyx artifact",
            "log": "lower-scf-to-calyx.log",
            "normalized_input": "flat.scf.mlir",
        },
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
