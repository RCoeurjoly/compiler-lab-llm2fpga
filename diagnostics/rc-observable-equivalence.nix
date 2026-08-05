{ pkgs
, python
, pythonWithTinyStoriesTorchAO
, sv
, image
, exportedProgram
, f32ConstantBits
, flatScf
, calyx
, sourceRoot
}:

let
  runner = "${sourceRoot}/scripts/pipeline/run_rc_sv_equivalence.py";
  oracleBuilder = "${sourceRoot}/scripts/pipeline/build_rc_observable_oracle.py";
  frozenOracle = pkgs.runCommand "tinystories-w8a8-rc-observable-oracle-frozen-four" {
    nativeBuildInputs = [ pythonWithTinyStoriesTorchAO pkgs.bash ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"
    generate() {
      local case_name="$1"
      local index="$2"
      ${pythonWithTinyStoriesTorchAO}/bin/python ${oracleBuilder} generate \
        --exported-program-dir ${exportedProgram} \
        --reference ${image}/reference.json \
        --image ${image}/rc-image.bin \
        --image-manifest ${image}/rc-image-manifest.json \
        --output-dir "$out" \
        --start "$index" --stop "$((index + 1))"
      mv "$out/shard-$index-$((index + 1)).json" "$out/$case_name.json"
    }
    generate ascending 67141
    generate descending 1612474
    generate zeros 0
    generate alternating 239945
  '';

  strictBuild = pkgs.runCommand "tinystories-w8a8-rc-observable-equivalence-build" {
    nativeBuildInputs = [ python pkgs.bash pkgs.verilator pkgs.gnumake pkgs.stdenv.cc ];
  } ''
    set -euo pipefail
    export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"
    ${python}/bin/python3 ${runner} \
      --equivalence-shard ${frozenOracle}/zeros.json \
      --f32-constant-bits ${f32ConstantBits} \
      --f32-calyx-mlir ${sv}/constant-proof/normalized.calyx.mlir \
      --f32-raw-futil ${sv}/constant-proof/exported.raw.futil \
      --flat-scf ${flatScf}/flat.scf.mlir \
      --pre-calyx ${calyx}/pre-calyx.mlir \
      --sv ${sv}/sv/main.sv \
      --image ${image}/rc-image.bin \
      --manifest ${image}/rc-image-manifest.json \
      --verilator ${pkgs.verilator}/bin/verilator \
      --verilate-jobs 4 --build-jobs 4 \
      --verilator-threads 8 \
      --verilator-output-split 10000 \
      --verilator-output-split-cfuncs 10000 \
      --work-dir "$out/verilator-work" \
      --timing-json "$out/compile-timing.json" \
      --compile-only
  '';

  frozenFour = pkgs.runCommand "tinystories-w8a8-rc-observable-equivalence-frozen-four" {
    nativeBuildInputs = [ python pkgs.bash pkgs.coreutils pkgs.verilator ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"
    cp -r ${strictBuild}/verilator-work "$out/verilator-work"
    for case_name in ascending descending zeros alternating; do
      ${python}/bin/python3 ${runner} \
        --equivalence-shard ${frozenOracle}/$case_name.json \
        --f32-constant-bits ${f32ConstantBits} \
        --f32-calyx-mlir ${sv}/constant-proof/normalized.calyx.mlir \
        --f32-raw-futil ${sv}/constant-proof/exported.raw.futil \
        --flat-scf ${flatScf}/flat.scf.mlir \
        --pre-calyx ${calyx}/pre-calyx.mlir \
        --sv ${sv}/sv/main.sv \
        --image ${image}/rc-image.bin \
        --manifest ${image}/rc-image-manifest.json \
        --verilator ${pkgs.verilator}/bin/verilator \
        --work-dir "$out/verilator-work" \
        --verify-cache --run-only \
        --result-json "$out/$case_name.json"
    done
    ${python}/bin/python3 ${runner} \
      --equivalence-sequence \
        ${frozenOracle}/ascending.json \
        ${frozenOracle}/descending.json \
        ${frozenOracle}/zeros.json \
        ${frozenOracle}/alternating.json \
      --f32-constant-bits ${f32ConstantBits} \
      --f32-calyx-mlir ${sv}/constant-proof/normalized.calyx.mlir \
      --f32-raw-futil ${sv}/constant-proof/exported.raw.futil \
      --flat-scf ${flatScf}/flat.scf.mlir \
      --pre-calyx ${calyx}/pre-calyx.mlir \
      --sv ${sv}/sv/main.sv \
      --image ${image}/rc-image.bin \
      --manifest ${image}/rc-image-manifest.json \
      --verilator ${pkgs.verilator}/bin/verilator \
      --work-dir "$out/verilator-work" \
      --verify-cache --run-only \
      --result-json "$out/sequential-reset.json"
    ${python}/bin/python3 ${runner} \
      --reduce-frozen-four \
      --f32-constant-bits ${f32ConstantBits} \
      --fresh-receipt ascending="$out/ascending.json" \
      --fresh-receipt descending="$out/descending.json" \
      --fresh-receipt zeros="$out/zeros.json" \
      --fresh-receipt alternating="$out/alternating.json" \
      --sequential-receipt "$out/sequential-reset.json" \
      --result-json "$out/summary.json"
  '';
in {
  inherit frozenOracle strictBuild frozenFour;
}
