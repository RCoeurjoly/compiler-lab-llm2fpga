#!/usr/bin/env bash
set -euo pipefail

circt_opt="${1:?usage: calyx_to_sv <circt-opt> <calyx-dir> <output-dir>}"
input_dir="${2:?usage: calyx_to_sv <circt-opt> <calyx-dir> <output-dir>}"
output_dir="${3:?usage: calyx_to_sv <circt-opt> <calyx-dir> <output-dir>}"

if [[ ! -x "$circt_opt" ]]; then
  echo "not executable: $circt_opt" >&2
  exit 2
fi

manifest="$input_dir/manifest.json"
input="$input_dir/model.calyx.mlir"

mkdir -p "$output_dir/logs"
cp "$manifest" "$output_dir/calyx-manifest.json"

if ! grep -q '"status":"ok"' "$manifest"; then
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

tmp_log="$(mktemp /tmp/calyx_to_sv_XXXXXX.log)"
cleanup() {
  rm -f "$tmp_log"
}
trap cleanup EXIT

mkdir -p "$output_dir/sv"

set +e
"$circt_opt" "$input" \
  --lower-calyx-to-hw \
  --lower-hw-to-sv \
  --export-verilog \
  >"$output_dir/sv/main.sv" 2>"$tmp_log"
rc=$?
set -e

cp "$tmp_log" "$output_dir/logs/calyx-to-sv.log"

if [[ "$rc" -ne 0 || ! -s "$output_dir/sv/main.sv" ]]; then
  echo "Calyx-to-SV failed." >&2
  sed -n '1,160p' "$tmp_log" >&2
  rm -f "$output_dir/sv/main.sv"
  exit 1
fi

cat >"$output_dir/sources.f" <<EOF
$output_dir/sv/main.sv
EOF

cat >"$output_dir/manifest.json" <<'JSON'
{"stage":"calyx-sv","status":"ok","sources":"sources.f"}
JSON
