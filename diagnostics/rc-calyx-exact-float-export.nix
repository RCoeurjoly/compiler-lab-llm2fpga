{ pkgs, circt }:

pkgs.runCommand "rc-calyx-exact-float-export" {
  nativeBuildInputs = [ circt pkgs.python3 ];
} ''
  set -euo pipefail
  mkdir -p "$out"
  ${circt}/bin/circt-translate --export-calyx \
    ${../reproducers/calyx-exact-float-export/input.mlir} \
    -o "$out/export.futil"
  ${pkgs.python3}/bin/python3 - "$out/export.futil" "$out/receipt.json" <<'PY'
import json
import pathlib
import sys

export_path = pathlib.Path(sys.argv[1])
receipt_path = pathlib.Path(sys.argv[2])
exported = export_path.read_text(encoding="utf-8")
expected = {
    "tiny": 866258955,
    "neg_zero": 2147483648,
    "pos_inf": 2139095040,
    "nan": 2143289345,
    "four_point_two": 1082549862,
}
for name, raw_word in expected.items():
    line = f"{name} = std_const(32, {raw_word});"
    if line not in exported:
        raise SystemExit(f"missing exact raw-word constant: {line}")
for forbidden in ("std_float_const", "primitives/float.futil"):
    if forbidden in exported:
        raise SystemExit(f"unexpected float-constant export dependency: {forbidden}")
receipt_path.write_text(
    json.dumps({
        "status": "pass",
        "constants": expected,
        "export": "export.futil",
    }, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
''
