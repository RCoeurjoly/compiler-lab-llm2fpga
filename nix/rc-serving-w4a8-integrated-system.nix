{ pkgs, pythonWithTinyStoriesTorchAO, tinyStories1m, phaseOracle, sourceRoot }:
let
  modelKey = "tinystories-w4a8-rc-serving-integrated";
  trace = "${sourceRoot}/TinyStories/rc_serving_trace_input.json";
  materializer =
    "${sourceRoot}/scripts/pipeline/materialize_rc_serving_w4a8_integrated.py";

  pytorchExported = pkgs.runCommand
    "${modelKey}-pytorch-exported"
    {
      nativeBuildInputs = [ pythonWithTinyStoriesTorchAO ];
      exportedProgramCount = 1;
      preferLocalBuild = true;
      allowSubstitutes = false;
    }
    ''
      set -euo pipefail
      export PYTHONPATH="${sourceRoot}:''${PYTHONPATH:-}"
      ${pythonWithTinyStoriesTorchAO}/bin/python ${materializer} \
        --model-path ${tinyStories1m.snapshot} \
        --trace ${trace} \
        --phase-oracle ${phaseOracle} \
        --out-dir "$out"
    '';

  reference = pkgs.runCommand "${modelKey}-reference" { } ''
    set -euo pipefail
    mkdir -p "$out"
    ln -s ${pytorchExported}/observation.json "$out/observation.json"
    ln -s ${pytorchExported}/readback-manifest.json "$out/readback-manifest.json"
    ln -s ${pytorchExported}/receipt.json "$out/receipt.json"
  '';
in {
  inherit modelKey pytorchExported reference;
}
