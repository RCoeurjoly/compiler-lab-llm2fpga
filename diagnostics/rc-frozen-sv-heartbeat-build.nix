{ pkgs
, sv
, image
}:

pkgs.runCommand "tinystories-w8a8-rc-frozen-sv-heartbeat-build" {
  nativeBuildInputs = [
    pkgs.python3
    pkgs.bash
    pkgs.verilator
    pkgs.gnumake
    pkgs.stdenv.cc
  ];
} ''
  set -euo pipefail
  ${pkgs.python3}/bin/python3 ${../scripts/pipeline/run_rc_sv_equivalence.py} \
    --sv ${sv}/sv/main.sv \
    --image ${image}/rc-image.bin \
    --manifest ${image}/rc-image-manifest.json \
    --reference ${image}/reference.json \
    --verilator ${pkgs.verilator}/bin/verilator \
    --verilator-output-split 10000 \
    --verilator-output-split-cfuncs 10000 \
    --verilator-jobs 8 \
    --heartbeat-cycles 1 \
    --work-dir "$out/verilator-work" \
    --compile-only
''
