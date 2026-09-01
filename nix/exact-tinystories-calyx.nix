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
  ${python}/bin/python3 ${runner} \
    --validate-predecessor ${predecessor} \
    --expected-prepared-sha256 ${expectedPreparedSha256} \
    --expected-receipt-sha256 ${expectedReceiptSha256}
  ${python}/bin/python3 ${runner} \
    --input ${predecessor}/pre-calyx.mlir \
    --output "$out" \
    --circt-opt ${circt}/bin/circt-opt
  ${python}/bin/python3 ${runner} --validate-output "$out"
''
