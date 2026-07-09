#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compile_primitives_to_sv="${CALYX_COMPILE_PRIMITIVES_TO_SV:-$SCRIPT_DIR/calyx_compile_primitives_to_sv.py}"

circt_translate="${1:?usage: calyx_to_sv <circt-translate> <calyx-bin> <calyx-lib-dir> <calyx-dir> <output-dir>}"
calyx_bin="${2:?usage: calyx_to_sv <circt-translate> <calyx-bin> <calyx-lib-dir> <calyx-dir> <output-dir>}"
calyx_lib="${3:?usage: calyx_to_sv <circt-translate> <calyx-bin> <calyx-lib-dir> <calyx-dir> <output-dir>}"
input_dir="${4:?usage: calyx_to_sv <circt-translate> <calyx-bin> <calyx-lib-dir> <calyx-dir> <output-dir>}"
output_dir="${5:?usage: calyx_to_sv <circt-translate> <calyx-bin> <calyx-lib-dir> <calyx-dir> <output-dir>}"

if [[ ! -x "$circt_translate" ]]; then
  echo "not executable: $circt_translate" >&2
  exit 2
fi

if [[ ! -x "$calyx_bin" ]]; then
  echo "not executable: $calyx_bin" >&2
  exit 2
fi

if [[ ! -d "$calyx_lib/primitives" ]]; then
  echo "missing Calyx primitives: $calyx_lib/primitives" >&2
  exit 2
fi

manifest="$input_dir/manifest.json"
input="$input_dir/model.calyx.mlir"

mkdir -p "$output_dir/logs"
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

tmp_export_log="$(mktemp /tmp/calyx_export_XXXXXX.log)"
tmp_calyx_log="$(mktemp /tmp/calyx_to_sv_XXXXXX.log)"
cleanup() {
  rm -f "$tmp_export_log" "$tmp_calyx_log"
}
trap cleanup EXIT

mkdir -p "$output_dir/sv"

set +e
"$circt_translate" --export-calyx "$input" \
  -o "$output_dir/model.futil" >"$tmp_export_log" 2>&1
rc=$?
set -e

cp "$tmp_export_log" "$output_dir/logs/export-calyx.log"

if [[ "$rc" -ne 0 || ! -s "$output_dir/model.futil" ]]; then
  echo "CIRCT Calyx export failed." >&2
  sed -n '1,160p' "$tmp_export_log" >&2
  rm -f "$output_dir/model.futil"
  exit 1
fi

missing_imports=()
while IFS= read -r import_path; do
  if [[ ! -f "$calyx_lib/$import_path" ]]; then
    missing_imports+=("$import_path")
  fi
done < <(sed -n 's/^import "\([^"]*\)";$/\1/p' "$output_dir/model.futil")

if [[ "${#missing_imports[@]}" -ne 0 ]]; then
  {
    echo "CIRCT exported Futil that is incompatible with the packaged Calyx library."
    echo "Missing imported primitive files under: $calyx_lib"
    for import_path in "${missing_imports[@]}"; do
      echo "  - $import_path"
    done
    echo "Use a version-aligned official Calyx library, remove the unsupported path before Calyx, or fix the backend with a real compiler change."
  } >&2
  printf '%s\n' "${missing_imports[@]}" >"$output_dir/logs/missing-calyx-imports.txt"
  exit 1
fi

set +e
"$calyx_bin" "$output_dir/model.futil" \
  -l "$calyx_lib" \
  -b verilog \
  --synthesis \
  --nested \
  -d papercut \
  -o "$output_dir/sv/main.sv" >"$tmp_calyx_log" 2>&1
rc=$?
set -e

cp "$tmp_calyx_log" "$output_dir/logs/native-calyx-to-sv.log"

if [[ "$rc" -ne 0 || ! -s "$output_dir/sv/main.sv" ]]; then
  echo "Native Calyx-to-SV failed." >&2
  sed -n '1,160p' "$tmp_calyx_log" >&2
  rm -f "$output_dir/sv/main.sv"
  exit 1
fi

python3 "$compile_primitives_to_sv" \
  --compile-futil "$calyx_lib/primitives/compile.futil" \
  --output "$output_dir/sv/compile.sv"

set +e
"$calyx_bin" "$output_dir/model.futil" \
  -l "$calyx_lib" \
  -b resources \
  --synthesis \
  -d papercut \
  -o "$output_dir/resources.csv" >"$output_dir/logs/native-calyx-resources.log" 2>&1
rc=$?
set -e

if [[ "$rc" -ne 0 || ! -s "$output_dir/resources.csv" ]]; then
  echo "Native Calyx resource report failed." >&2
  sed -n '1,160p' "$output_dir/logs/native-calyx-resources.log" >&2
  rm -f "$output_dir/resources.csv"
  exit 1
fi

python3 - "$output_dir/logs/native-calyx-resources.log" "$output_dir/resources.json" <<'PY'
import json
import re
import sys
from pathlib import Path

log = Path(sys.argv[1]).read_text(encoding="utf-8")
summary = {
    "status": "ok",
    "backend": "native-calyx-resources",
    "estimated_internal_bits": None,
    "estimated_external_bits": None,
}
internal = re.search(r"Estimated size in bit\(s\):\s*(\d+)", log)
external = re.search(r"Estimated external size in bit\(s\):\s*(\d+)", log)
if internal:
    summary["estimated_internal_bits"] = int(internal.group(1))
if external:
    summary["estimated_external_bits"] = int(external.group(1))
Path(sys.argv[2]).write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
PY

cat >"$output_dir/sources.f" <<EOF
$output_dir/sv/compile.sv
$calyx_lib/primitives/core.sv
$calyx_lib/primitives/binary_operators.sv
$calyx_lib/primitives/memories/seq.sv
$output_dir/sv/main.sv
EOF

cat >"$output_dir/manifest.json" <<'JSON'
{"backend":"native-calyx","resources":"resources.json","stage":"calyx-sv","status":"ok","sources":"sources.f"}
JSON
