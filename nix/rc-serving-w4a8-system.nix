{ pkgs, pythonWithTinyStoriesTorchAO, tinyStories1m, sourceRoot }:
let
  modelKey = "tinystories-w4a8-rc-serving-mask10-vocab6-width2";
  trace = "${sourceRoot}/TinyStories/rc_serving_trace_input.json";
  materializer = "${sourceRoot}/scripts/pipeline/materialize_rc_serving_w4a8.py";
  schema_version = 1;

  frozenBundle = pkgs.runCommand "${modelKey}-frozen-bundle" {
    nativeBuildInputs = [ pythonWithTinyStoriesTorchAO pkgs.diffutils ];
  } ''
    set -euo pipefail
    export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"
    ${pythonWithTinyStoriesTorchAO}/bin/python ${materializer} \
      --model-path ${tinyStories1m.snapshot} --trace ${trace} --out-dir "$out"
    ${pythonWithTinyStoriesTorchAO}/bin/python ${materializer} \
      --model-path ${tinyStories1m.snapshot} --trace ${trace} --out-dir repeat
    cmp "$out/manifest.json" repeat/manifest.json
    cmp "$out/frozen/manifest.json" repeat/frozen/manifest.json
    cmp "$out/frozen/weights.bin" repeat/frozen/weights.bin
  '';

  phasePackage = phase: name:
    pkgs.runCommand "${modelKey}-${name}-pytorch-exported" { } ''
      set -euo pipefail
      mkdir -p "$out"
      ln -s ${frozenBundle}/${phase}/exported.pt2 "$out/exported.pt2"
      ln -s ${frozenBundle}/${phase}/graph.txt "$out/graph.txt"
      ln -s ${frozenBundle}/${phase}/graph-module.py "$out/graph-module.py"
      ln -s ${frozenBundle}/${phase}/graph-signature.txt "$out/graph-signature.txt"
      ln -s ${frozenBundle}/${phase}/reference.json "$out/reference.json"
      ln -s ${frozenBundle}/frozen/manifest.json "$out/w4a8-manifest.json"
      ln -s ${frozenBundle}/frozen/weights.bin "$out/weights.bin"
    '';

  prefill8PytorchExported = phasePackage "prefill-8" "prefill-8";
  decode8PytorchExported = phasePackage "decode-8" "decode-8";
  decode9PytorchExported = phasePackage "decode-9" "decode-9";
in {
  inherit modelKey frozenBundle prefill8PytorchExported
    decode8PytorchExported decode9PytorchExported;
}
