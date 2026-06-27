#!/usr/bin/env bash
set -euo pipefail

circt_opt="${1:?usage: scf_to_flat_scf_no_handshake.sh <circt-opt> <input-scf-mlir> <output-dir>}"
input="${2:?usage: scf_to_flat_scf_no_handshake.sh <circt-opt> <input-scf-mlir> <output-dir>}"
output_dir="${3:?usage: scf_to_flat_scf_no_handshake.sh <circt-opt> <input-scf-mlir> <output-dir>}"
blocker_report="${FLAT_SCF_BLOCKER_REPORT:?set FLAT_SCF_BLOCKER_REPORT to flat_scf_blocker_report.py}"

if [[ ! -x "$circt_opt" ]]; then
  echo "not executable: $circt_opt" >&2
  exit 2
fi

if [[ ! -f "$input" ]]; then
  echo "missing input MLIR: $input" >&2
  exit 2
fi

tmp_flat="$(mktemp /tmp/no_handshake_flat_scf_XXXXXX.mlir)"
tmp_expanded="$(mktemp /tmp/no_handshake_flat_scf_expanded_XXXXXX.mlir)"
cleanup() {
  rm -f "$tmp_flat" "$tmp_expanded"
}
trap cleanup EXIT

mkdir -p "$output_dir"

"$circt_opt" "$input" \
  --flatten-memref \
  --canonicalize \
  --cse \
  -o "$tmp_flat"

python3 - "$tmp_flat" "$tmp_expanded" <<'PY'
import re
import sys
from pathlib import Path

COPY_RE = re.compile(
    r"^(?P<indent>\s*)memref\.copy (?P<src>%[\w$.]+), (?P<dst>%[\w$.]+) : "
    r"(?P<src_ty>memref<(?P<src_body>[^>]+)>) to (?P<dst_ty>memref<(?P<dst_body>[^>]+)>)\s*$"
)


def parse_static_shape(body: str) -> tuple[list[int], str] | None:
    parts = body.split("x")
    if len(parts) < 2:
        return None

    dims: list[int] = []
    for part in parts[:-1]:
        if not part.isdigit():
            return None
        dims.append(int(part))
    return dims, parts[-1]


def expand_copy(match: re.Match[str], ordinal: int) -> list[str] | None:
    src_shape = parse_static_shape(match.group("src_body"))
    dst_shape = parse_static_shape(match.group("dst_body"))
    if src_shape is None or dst_shape is None or src_shape != dst_shape:
        return None

    dims, _element_type = src_shape
    if not dims:
        return None

    indent = match.group("indent")
    src = match.group("src")
    dst = match.group("dst")
    src_ty = match.group("src_ty")
    dst_ty = match.group("dst_ty")

    lines: list[str] = []
    zero = f"%copy{ordinal}_c0"
    one = f"%copy{ordinal}_c1"
    lines.append(f"{indent}{zero} = arith.constant 0 : index")
    lines.append(f"{indent}{one} = arith.constant 1 : index")

    loop_indent = indent
    indices: list[str] = []
    for depth, dim in enumerate(dims):
        bound = f"%copy{ordinal}_c{dim}_{depth}"
        index = f"%copy{ordinal}_i{depth}"
        lines.append(f"{indent}{bound} = arith.constant {dim} : index")
        lines.append(f"{loop_indent}scf.for {index} = {zero} to {bound} step {one} {{")
        indices.append(index)
        loop_indent += "  "

    index_list = ", ".join(indices)
    value = f"%copy{ordinal}_value"
    lines.append(f"{loop_indent}{value} = memref.load {src}[{index_list}] : {src_ty}")
    lines.append(f"{loop_indent}memref.store {value}, {dst}[{index_list}] : {dst_ty}")

    for depth in reversed(range(len(dims))):
        close_indent = indent + ("  " * depth)
        lines.append(f"{close_indent}}}")

    return lines


output: list[str] = []
copy_ordinal = 0
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    match = COPY_RE.match(line)
    if not match:
        output.append(line)
        continue

    expanded = expand_copy(match, copy_ordinal)
    if expanded is None:
        output.append(line)
        continue

    output.extend(expanded)
    copy_ordinal += 1

Path(sys.argv[2]).write_text("\n".join(output) + "\n", encoding="utf-8")
PY

cp "$tmp_expanded" "$output_dir/flat.scf.mlir"

python3 "$blocker_report" \
  --input "$output_dir/flat.scf.mlir" \
  --output "$output_dir/blockers.json"

python3 - "$output_dir/blockers.json" "$output_dir/manifest.json" <<'PY'
import json
import sys
from pathlib import Path

blocker_report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
status = "ok" if not blocker_report["blockers"] else "blocked"

Path(sys.argv[2]).write_text(
    json.dumps(
        {
            "stage": "flat-scf",
            "status": status,
            "artifact": "flat.scf.mlir",
            "blockers": "blockers.json",
        },
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
