#!/usr/bin/env bash
set -euo pipefail

circt_opt="${1:?usage: calyx_to_hw_sv_no_handshake.sh <circt-opt> <calyx-dir> <output-dir>}"
input_dir="${2:?usage: calyx_to_hw_sv_no_handshake.sh <circt-opt> <calyx-dir> <output-dir>}"
output_dir="${3:?usage: calyx_to_hw_sv_no_handshake.sh <circt-opt> <calyx-dir> <output-dir>}"
manifest="$input_dir/manifest.json"
input="$input_dir/model.calyx.mlir"

if [[ ! -x "$circt_opt" ]]; then
  echo "not executable: $circt_opt" >&2
  exit 2
fi

if [[ ! -f "$manifest" ]]; then
  echo "missing manifest: $manifest" >&2
  exit 2
fi

mkdir -p "$output_dir/logs" "$output_dir/sv"
cp "$manifest" "$output_dir/calyx-manifest.json"

manifest_status="$(
  python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("status", ""))
PY
)"

if [[ "$manifest_status" != "ok" ]]; then
  echo "Calyx handoff is not available; refusing to emit placeholder SV." >&2
  if [[ -f "$input_dir/lower-scf-to-calyx.log" ]]; then
    cp "$input_dir/lower-scf-to-calyx.log" "$output_dir/logs/"
    sed -n '1,160p' "$input_dir/lower-scf-to-calyx.log" >&2
  fi
  exit 1
fi

if [[ ! -f "$input" ]]; then
  echo "missing Calyx MLIR: $input" >&2
  exit 2
fi

plugin_args=()
if [[ -n "${CIRCT_PASS_PLUGIN:-}" ]]; then
  if [[ ! -f "$CIRCT_PASS_PLUGIN" ]]; then
    echo "missing CIRCT pass plugin: $CIRCT_PASS_PLUGIN" >&2
    exit 2
  fi
  plugin_args=( "--load-pass-plugin=$CIRCT_PASS_PLUGIN" )
fi

tmp_preflight="$(mktemp /tmp/calyx_hw_preflight_XXXXXX.mlir)"
tmp_preflight_log="$(mktemp /tmp/calyx_hw_preflight_XXXXXX.log)"
tmp_log="$(mktemp /tmp/calyx_hw_sv_XXXXXX.log)"
cleanup() {
  rm -f "$tmp_preflight" "$tmp_preflight_log" "$tmp_log"
}
trap cleanup EXIT

set +e
"$circt_opt" \
  "${plugin_args[@]}" \
  "$input" \
  --pass-pipeline='builtin.module(llm2fpga-calyx-hw-preflight)' \
  -o "$tmp_preflight" >"$tmp_preflight_log" 2>&1
rc=$?
set -e

cp "$tmp_preflight_log" "$output_dir/logs/calyx-hw-preflight.log"

if [[ "$rc" -ne 0 || ! -s "$tmp_preflight" ]]; then
  echo "Direct CIRCT Calyx-to-HW/SV preflight failed." >&2
  sed -n '1,160p' "$tmp_preflight_log" >&2
  rm -f "$output_dir/sv/main.sv"
  cat >"$output_dir/manifest.json" <<'JSON'
{"backend":"calyx-hw-sv","log":"logs/calyx-hw-preflight.log","stage":"calyx-hw-sv","status":"failed"}
JSON
  exit 1
fi

set +e
"$circt_opt" "$tmp_preflight" \
  --calyx-remove-groups \
  --lower-calyx-to-hw \
  --canonicalize \
  --cse \
  --lower-seq-to-sv \
  --lower-hw-to-sv \
  --canonicalize \
  --cse \
  --strip-debuginfo-with-pred="drop-suffix=.mlir" \
  --export-verilog \
  -o /dev/null >"$output_dir/sv/main.sv" 2>"$tmp_log"
rc=$?
set -e

cp "$tmp_log" "$output_dir/logs/calyx-hw-sv.log"

if [[ "$rc" -ne 0 || ! -s "$output_dir/sv/main.sv" ]]; then
  echo "Direct CIRCT Calyx-to-HW/SV failed." >&2
  sed -n '1,160p' "$tmp_log" >&2
  rm -f "$output_dir/sv/main.sv"
  cat >"$output_dir/manifest.json" <<'JSON'
{"backend":"calyx-hw-sv","log":"logs/calyx-hw-sv.log","stage":"calyx-hw-sv","status":"failed"}
JSON
  exit 1
fi

find "$output_dir/sv" -type f -name '*.sv' | sort >"$output_dir/sources.f"
cat >"$output_dir/manifest.json" <<'JSON'
{"backend":"calyx-hw-sv","stage":"calyx-hw-sv","status":"ok","sources":"sources.f"}
JSON
