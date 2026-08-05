{ pkgs
, python
, pythonWithTinyStoriesTorchAO
, sv
, image
, exportedProgram
, f32ConstantBits
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
      --sv ${sv}/sv/main.sv \
      --image ${image}/rc-image.bin \
      --manifest ${image}/rc-image-manifest.json \
      --verilator ${pkgs.verilator}/bin/verilator \
      --work-dir "$out/verilator-work" \
      --verify-cache --run-only \
      --result-json "$out/sequential-reset.json"
    ${python}/bin/python3 - "$out" "${f32ConstantBits}" "${runner}" <<'PY'
import hashlib
import importlib.util
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
proof_sha256 = hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).hexdigest()
runner = pathlib.Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("rc_equivalence_runner", runner)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load strict equivalence reducer")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
names = ["ascending", "descending", "zeros", "alternating"]
fresh = {
    name: json.loads((out / f"{name}.json").read_text(encoding="utf-8"))
    for name in names
}
sequential = json.loads((out / "sequential-reset.json").read_text(encoding="utf-8"))
summary = module._frozen_four_summary(names, fresh, sequential, proof_sha256)
(out / "summary.json").write_text(
    json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8"
)
PY
  '';
in {
  inherit frozenOracle strictBuild frozenFour;
}
