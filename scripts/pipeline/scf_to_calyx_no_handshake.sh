#!/usr/bin/env bash
set -euo pipefail

circt_opt="${1:?usage: scf_to_calyx_no_handshake.sh <circt-opt> <input-flat-scf-mlir> <output-dir>}"
input="${2:?usage: scf_to_calyx_no_handshake.sh <circt-opt> <input-flat-scf-mlir> <output-dir>}"
output_dir="${3:?usage: scf_to_calyx_no_handshake.sh <circt-opt> <input-flat-scf-mlir> <output-dir>}"
calyx_preflight_report="${CALYX_PREFLIGHT_REPORT:-}"

if [[ ! -x "$circt_opt" ]]; then
  echo "not executable: $circt_opt" >&2
  exit 2
fi

if [[ ! -f "$input" ]]; then
  echo "missing input MLIR: $input" >&2
  exit 2
fi

tmp_log="$(mktemp /tmp/no_handshake_calyx_XXXXXX.log)"
cleanup() {
  rm -f "$tmp_log"
}
trap cleanup EXIT

mkdir -p "$output_dir"

cp "$input" "$output_dir/flat.scf.mlir"

if [[ -n "$calyx_preflight_report" ]]; then
  set +e
  python3 "$calyx_preflight_report" "$input" \
    "$output_dir/pre-calyx-legality.json" --require-clean
  preflight_rc=$?
  set -e

  if [[ "$preflight_rc" -ne 0 ]]; then
    printf '%s\n' \
      '{"stage":"calyx","status":"failed","reason":"pre-Calyx legality census found prohibited operations","normalized_input":"flat.scf.mlir","preflight":"pre-calyx-legality.json"}' \
      >"$output_dir/manifest.json"
    exit 0
  fi
fi

set +e
"$circt_opt" "$input" \
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
