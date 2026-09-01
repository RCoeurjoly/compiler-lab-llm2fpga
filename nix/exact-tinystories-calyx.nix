{ pkgs, circt, python, predecessor }:
let
  expectedPreparedSha256 = "54a7df3fec336c5418d3562441a3f9affe45702eb107b89092bc2f7b53afca31";
  expectedReceiptSha256 = "451628dba61ea805b09007e89b2135d00dcd93cf225ed4d6d9625a05a598de30";
  runner = ../scripts/pipeline/run_exact_tinystories_calyx.py;
in
pkgs.runCommand "tiny-stories-1m-kev-gpt-exact-calyx-frontier" {
  nativeBuildInputs = [ pkgs.coreutils circt python ];
} ''
  set -euo pipefail
  export NIX_DERIVATION="$out"
  ${python}/bin/python3 -c '
import hashlib
import json
import sys
from pathlib import Path

predecessor = Path(sys.argv[1])
expected_prepared, expected_receipt = sys.argv[2:]
manifest = json.loads((predecessor / "manifest.json").read_text(encoding="utf-8"))
if manifest.get("calyx_authorized") is not True:
    raise SystemExit("predecessor calyx_authorized must be true")
for name, expected in (("pre-calyx.mlir", expected_prepared), ("pre-calyx-legality.json", expected_receipt)):
    actual = hashlib.sha256((predecessor / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"predecessor {name} SHA-256 mismatch")
' ${predecessor} ${expectedPreparedSha256} ${expectedReceiptSha256}
  ${python}/bin/python3 ${runner} \
    --input ${predecessor}/pre-calyx.mlir \
    --output "$out" \
    --circt-opt ${circt}/bin/circt-opt
  test -f "$out/manifest.json"
  test -f "$out/lower-scf-to-calyx.log"
  test -f "$out/model.calyx.mlir" -o -f "$out/partial.calyx.mlir"
''
