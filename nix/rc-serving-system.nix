{ pkgs, pythonWithTinyStoriesTorchAO, tinyStories1m, sourceRoot }:
let
  modelKey = "tinystories-w8a8-rc-serving-mask10-vocab6-width2";
  trace = "${sourceRoot}/TinyStories/rc_serving_trace_input.json";
  referenceBuilder = "${sourceRoot}/scripts/pipeline/build_rc_serving_reference.py";
  directMaterializer =
    "${sourceRoot}/scripts/pipeline/materialize_rc_serving_direct_exports.py";
  modelMetadata = pkgs.writeText
    "tinystories-w8a8-rc-serving-mask10-vocab6-width2-metadata.json"
    (builtins.toJSON {
      schema_version = 1;
      model_key = modelKey;
      artifact_kind = "stateful-serving-profile";
      source = {
        type = "derived";
        profile = "stateful-serving-representative-core";
        base_model_id = tinyStories1m.modelId;
        revision = tinyStories1m.revision;
        vocab_size = 6;
        num_layers = 2;
        hidden_size = 2;
        num_heads = 1;
        window_size = 256;
        max_position_embeddings = 10;
        prompt_length = 8;
        decode_steps = 2;
      };
      quantization = {
        requested = "pt2e-static-w8a8";
        status = "probe-required";
      };
    });

  nativeReference = pkgs.runCommand "${modelKey}-native-reference" {
    nativeBuildInputs = [ pythonWithTinyStoriesTorchAO pkgs.diffutils ];
  } ''
    set -euo pipefail
    mkdir -p "$out/repeat"
    export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"
    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${referenceBuilder} \
      --model-path ${tinyStories1m.snapshot} \
      --trace ${trace} \
      --out "$out/reference.json"
    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${referenceBuilder} \
      --model-path ${tinyStories1m.snapshot} \
      --trace ${trace} \
      --out "$out/repeat/reference.json"
    ${pkgs.diffutils}/bin/cmp "$out/reference.json" "$out/repeat/reference.json"
  '';

  directExportBundle = pkgs.runCommand "${modelKey}-direct-export-bundle" {
    nativeBuildInputs = [ pythonWithTinyStoriesTorchAO ];
    propagatedBuildInputs = [ nativeReference ];
  } ''
    set -euo pipefail
    export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"
    ${pythonWithTinyStoriesTorchAO}/bin/python \
      ${directMaterializer} \
      --model-path ${tinyStories1m.snapshot} \
      --trace ${trace} \
      --reference ${nativeReference}/reference.json \
      --out-dir "$out"
  '';

  phasePackage = phase: name:
    pkgs.runCommand "${modelKey}-${name}-pytorch-exported" { } ''
      set -euo pipefail
      mkdir -p "$out"
      ln -s ${directExportBundle}/${phase}/exported.pt2 "$out/exported.pt2"
      ln -s ${directExportBundle}/${phase}/manifest.json "$out/manifest.json"
      ln -s ${directExportBundle}/${phase}/graph.txt "$out/graph.txt"
      ln -s ${directExportBundle}/${phase}/graph-module.py "$out/graph-module.py"
      ln -s ${directExportBundle}/${phase}/graph-signature.txt "$out/graph-signature.txt"
      ln -s ${directExportBundle}/${phase}/conformance.json "$out/conformance.json"
    '';

  prefill8PytorchExported = phasePackage "prefill-8" "prefill-8";
  decode8PytorchExported = phasePackage "decode-8" "decode-8";
  decode9PytorchExported = phasePackage "decode-9" "decode-9";
in {
  inherit modelKey modelMetadata nativeReference directExportBundle
    prefill8PytorchExported decode8PytorchExported decode9PytorchExported;
}
