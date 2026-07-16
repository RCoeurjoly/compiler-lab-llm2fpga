{ pkgs, pythonWithTinyStoriesTorchAO, exportedProgram, flatScf, calyx, sourceRoot
, sourceModelKey, pipelineAlias }:
let
  referenceImage = pkgs.runCommand "tinystories-w8a8-rc-reference-image" {
    nativeBuildInputs = [ pythonWithTinyStoriesTorchAO pkgs.coreutils pkgs.diffutils pkgs.gawk pkgs.jq ];
  } ''
    set -euo pipefail
    mkdir -p "$out/repeat"
    export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"

    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${sourceRoot}/scripts/pipeline/build_rc_working_reference.py \
      --exported-program-dir ${exportedProgram} \
      --corpus ${sourceRoot}/TinyStories/rc_working_corpus.json \
      --source-model-key ${sourceModelKey} \
      --pipeline-alias ${pipelineAlias} \
      --out "$out/reference.json"
    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${sourceRoot}/scripts/pipeline/build_rc_working_reference.py \
      --exported-program-dir ${exportedProgram} \
      --corpus ${sourceRoot}/TinyStories/rc_working_corpus.json \
      --source-model-key ${sourceModelKey} \
      --pipeline-alias ${pipelineAlias} \
      --out "$out/repeat/reference.json"
    ${pkgs.diffutils}/bin/cmp "$out/reference.json" "$out/repeat/reference.json"

    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${sourceRoot}/scripts/pipeline/pack_rc_working_image.py \
      --exported-program-dir ${exportedProgram} \
      --out-dir "$out"
    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${sourceRoot}/scripts/pipeline/pack_rc_working_image.py \
      --exported-program-dir ${exportedProgram} \
      --out-dir "$out/repeat"
    ${pkgs.diffutils}/bin/cmp "$out/rc-image.bin" "$out/repeat/rc-image.bin"
    ${pkgs.diffutils}/bin/cmp \
      "$out/rc-image-manifest.json" "$out/repeat/rc-image-manifest.json"

    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${sourceRoot}/scripts/pipeline/verify_rc_working_image.py \
      --exported-program-dir ${exportedProgram} \
      --image "$out/rc-image.bin" \
      --manifest "$out/rc-image-manifest.json" \
      --reference "$out/reference.json" \
      --corpus ${sourceRoot}/TinyStories/rc_working_corpus.json \
      --out "$out/image-replay.json"
    status="$(${pkgs.jq}/bin/jq -r .status "$out/image-replay.json")"
    if [ "$status" != "pass" ]; then
      echo "RC image replay status: $status" >&2
      exit 1
    fi

    ${pkgs.coreutils}/bin/sha256sum ${exportedProgram}/exported.pt2 \
      | ${pkgs.gawk}/bin/awk '{ print $1 }' > "$out/source-exported-sha256.txt"
    printf '%s\n' ${exportedProgram} > "$out/source-exported-path.txt"
  '';
  abiAudit = pkgs.runCommand "tinystories-w8a8-rc-abi-audit" {
    nativeBuildInputs = [ pkgs.coreutils pkgs.python3 ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    ${pkgs.python3}/bin/python3 \
      ${sourceRoot}/scripts/pipeline/audit_rc_sv_interface.py \
      --flat-scf ${flatScf}/flat.scf.mlir \
      --calyx-manifest ${calyx}/manifest.json \
      --calyx-log ${calyx}/lower-scf-to-calyx.log \
      --output "$out/interface.json"
    cp ${flatScf}/manifest.json "$out/flat-scf-manifest.json"
    cp ${calyx}/manifest.json "$out/calyx-manifest.json"
    cp ${calyx}/float-frontier.json "$out/float-frontier.json"
    cp ${calyx}/lower-scf-to-calyx.log "$out/lower-scf-to-calyx.log"
    if [ -f ${calyx}/model.calyx.mlir ]; then
      cp ${calyx}/model.calyx.mlir "$out/model.calyx.mlir"
    fi
  '';
in {
  inherit abiAudit referenceImage;
}
