{ pkgs, mlir, mlirPasses, python, c22Input, preflightScript
, expectedC22Sha256, expectedPluginSha256, expectedNormalizedSha256 }:
let
  normalizationPipeline =
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)";
  preparationPipeline =
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,llm2fpga-drop-calyx-unsupported-asserts,llm2fpga-fold-constant-truncf,llm2fpga-lower-roundeven-for-calyx,llm2fpga-lower-exact-math-for-calyx,llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)";
  plugin = "${mlirPasses}/lib/LLM2FPGAMLIRPasses.so";
in
pkgs.runCommand "tiny-stories-1m-kev-gpt-exact-normalized-flat-scf" {
  nativeBuildInputs = [ pkgs.coreutils mlir mlirPasses python ];
} ''
  set -euo pipefail
  mkdir -p "$out"

  c22_sha256="$(${pkgs.coreutils}/bin/sha256sum ${c22Input} | ${pkgs.coreutils}/bin/cut -d ' ' -f1)"
  test "$c22_sha256" = "${expectedC22Sha256}"
  plugin_sha256="$(${pkgs.coreutils}/bin/sha256sum ${plugin} | ${pkgs.coreutils}/bin/cut -d ' ' -f1)"
  test "$plugin_sha256" = "${expectedPluginSha256}"

  ${mlir}/bin/mlir-opt ${c22Input} \
    --load-pass-plugin=${plugin} \
    --pass-pipeline='${normalizationPipeline}' \
    -o "$out/flat.scf.mlir"
  flat_sha256="$(${pkgs.coreutils}/bin/sha256sum "$out/flat.scf.mlir" | ${pkgs.coreutils}/bin/cut -d ' ' -f1)"
  test "$flat_sha256" = "${expectedNormalizedSha256}"
  ${mlir}/bin/mlir-opt "$out/flat.scf.mlir" -o /dev/null

  raw_legality="$(mktemp)"
  ${python}/bin/python3 ${preflightScript} "$out/flat.scf.mlir" "$raw_legality" \
    --mlir-opt ${mlir}/bin/mlir-opt
  ${mlir}/bin/mlir-opt "$out/flat.scf.mlir" \
    --load-pass-plugin=${plugin} \
    --pass-pipeline='${preparationPipeline}' \
    -o "$out/pre-calyx.mlir"
  ${mlir}/bin/mlir-opt "$out/pre-calyx.mlir" -o /dev/null
  ${python}/bin/python3 ${preflightScript} "$out/pre-calyx.mlir" \
    "$out/pre-calyx-legality.json" --mlir-opt ${mlir}/bin/mlir-opt

  OUT_DIR="$out" RAW_LEGALITY="$raw_legality" \
    ${python}/bin/python3 - <<'PY'
  import hashlib
  import json
  import os
  from pathlib import Path

  out = Path(os.environ["OUT_DIR"])
  raw = json.loads(Path(os.environ["RAW_LEGALITY"]).read_text(encoding="utf-8"))
  legality = json.loads((out / "pre-calyx-legality.json").read_text(encoding="utf-8"))
  registered = (
      "memref.collapse_shape",
      "memref.copy",
      "memref.expand_shape",
      "memref.reinterpret_cast",
  )
  counts = {name: raw["prohibited_ops"].get(name, 0) for name in registered}
  if counts != {name: 0 for name in registered}:
      raise SystemExit("registered raw normalized blocker count is nonzero")
  def binding(path: Path):
      data = path.read_bytes()
      return {"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
  normalize = [
      "${mlir}/bin/mlir-opt", "${c22Input}",
      "--load-pass-plugin=${plugin}",
      "--pass-pipeline=${normalizationPipeline}", "-o", str(out / "flat.scf.mlir"),
  ]
  prepare = [
      "${mlir}/bin/mlir-opt", str(out / "flat.scf.mlir"),
      "--load-pass-plugin=${plugin}",
      "--pass-pipeline=${preparationPipeline}", "-o", str(out / "pre-calyx.mlir"),
  ]
  manifest = {
      "schema": "tinystories-1m-exact-normalized-registration-v1",
      "model": "tiny-stories-1m-kev-gpt-exact",
      "normalization": {
          "pipeline": "${normalizationPipeline}",
          "input": {"path": "c22-input.mlir", "sha256": "${expectedC22Sha256}"},
          "plugin": {"path": "${plugin}", "sha256": "${expectedPluginSha256}"},
          "output": binding(out / "flat.scf.mlir"),
          "registered_blocker_counts": counts,
      },
      "preparation": {
          "pipeline": "${preparationPipeline}",
          "input": binding(out / "flat.scf.mlir"),
          "output": binding(out / "pre-calyx.mlir"),
          "parse_status": "ok",
          "legality": {
              "path": "pre-calyx-legality.json",
              "sha256": hashlib.sha256((out / "pre-calyx-legality.json").read_bytes()).hexdigest(),
              "status": legality["status"],
              "receipt_sha256": legality["sha256"],
          },
      },
      "commands": {
          "normalize": normalize,
          "parse_flat": ["${mlir}/bin/mlir-opt", str(out / "flat.scf.mlir"), "-o", "/dev/null"],
          "prepare": prepare,
          "parse_prepared": ["${mlir}/bin/mlir-opt", str(out / "pre-calyx.mlir"), "-o", "/dev/null"],
          "preflight": ["${python}/bin/python3", "${preflightScript}", str(out / "pre-calyx.mlir"), str(out / "pre-calyx-legality.json"), "--mlir-opt", "${mlir}/bin/mlir-opt"],
      },
      "calyx_authorized": legality["status"] == "ok",
  }
  (out / "manifest.json").write_text(
      json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
      encoding="utf-8",
  )
  PY
  rm -f "$raw_legality"
''
