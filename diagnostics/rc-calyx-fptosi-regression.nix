{ pkgs, calyx, circt }:

pkgs.runCommand "rc-calyx-fptosi-latency" {
  nativeBuildInputs = [
    calyx
    circt
    pkgs.gnumake
    pkgs.gnugrep
    pkgs.python3
    pkgs.stdenv.cc
    pkgs.verilator
  ];
} ''
  set -euo pipefail
  mkdir -p "$out"

  ${circt}/bin/circt-opt \
    ${../reproducers/calyx-rc-basic-float-mrcs/fptosi-f32-i8.mlir} \
    --lower-scf-to-calyx='top-level-function=main' \
    -o "$out/model.calyx.mlir"
  ${circt}/bin/circt-translate --export-calyx \
    "$out/model.calyx.mlir" \
    -o "$out/model.futil"
  ${calyx}/bin/calyx "$out/model.futil" \
    -l ${calyx}/share/calyx \
    -b verilog \
    --synthesis \
    -o "$out/main.sv"
  ${pkgs.verilator}/bin/verilator \
    --binary \
    --timing \
    --top-module tb \
    --Wno-fatal \
    -Mdir "$out/obj_dir" \
    "$out/main.sv" \
    ${../reproducers/calyx-rc-basic-float-mrcs/fptosi-f32-i8.sv}

  set +e
  "$out/obj_dir/Vtb" > "$out/simulation.log" 2>&1
  simulator_status=$?
  set -e
  ${pkgs.coreutils}/bin/cat "$out/simulation.log"
  if [ "$simulator_status" -ne 0 ]; then
    exit "$simulator_status"
  fi

  ${pkgs.gnugrep}/bin/grep -F "FPTO_SI_MRC_PASS" "$out/simulation.log"
  ${pkgs.python3}/bin/python3 - "$out/simulation.log" "$out/result.json" <<'PY'
import json
import pathlib
import sys

log_path = pathlib.Path(sys.argv[1])
result_path = pathlib.Path(sys.argv[2])
log = log_path.read_text(encoding="utf-8")
cases = [
    ("plus_4_2", "40866666", 4),
    ("minus_1_7", "bfd9999a", -1),
    ("plus_127", "42fe0000", 127),
    ("minus_128", "c3000000", -128),
]
if "FPTO_SI_MRC_PASS" not in log:
    raise SystemExit("simulator exited zero without the fptosi pass marker")
for label, input_bits, expected in cases:
    expected_line = (
        f"FPTO_SI_CASE label={label} input_bits=0x{input_bits} "
        f"observed={expected} expected={expected}"
    )
    if expected_line not in log:
        raise SystemExit(f"missing verified case result: {expected_line}")
result_path.write_text(
    json.dumps(
        {
            "schema": "rc-calyx-fptosi-latency-v1",
            "status": "pass",
            "cases": [
                {
                    "label": label,
                    "input_bits": f"0x{input_bits}",
                    "expected_i8": expected,
                    "observed_i8": expected,
                }
                for label, input_bits, expected in cases
            ],
        },
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
  test -s "$out/result.json"
''
