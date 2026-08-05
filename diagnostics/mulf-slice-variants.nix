{ pkgs
, optimizer
, mlirOpt
, llvmLib
, runtime
, libxml2
, slice
, parallelSlice
, affineSlice
}:

pkgs.runCommand "tinystories-w8a8-mulf-slice-variants" {
  nativeBuildInputs = [ pkgs.python3 optimizer runtime libxml2 ];
} ''
  set -euo pipefail
  mkdir -p "$out"
  export LD_LIBRARY_PATH="${runtime}/lib:${libxml2}/lib:${mlirOpt}/lib:${llvmLib}/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  ${optimizer}/bin/torch-mlir-opt "${slice}" --canonicalize --cse -o "$out/baseline.mlir"
  ${optimizer}/bin/torch-mlir-opt "${slice}" \
    --loop-invariant-code-motion --canonicalize --cse \
    -o "$out/specialized.mlir"
  ${optimizer}/bin/torch-mlir-opt "${parallelSlice}" \
    --canonicalize --cse -o "$out/parallel.mlir"
  ${mlirOpt}/bin/mlir-opt "$out/parallel.mlir" \
    --convert-linalg-to-parallel-loops --canonicalize \
    -o "$out/parallel-loops.mlir"
  ${mlirOpt}/bin/mlir-opt "$out/parallel.mlir" \
    --pass-pipeline='builtin.module(func.func(convert-linalg-to-affine-loops,affine-parallelize),canonicalize)' \
    -o "$out/affine-parallel.mlir"
  ${mlirOpt}/bin/mlir-opt "${affineSlice}" \
    --pass-pipeline='builtin.module(func.func(affine-loop-unroll{unroll-factor=2}),lower-affine,canonicalize)' \
    -o "$out/affine-unrolled.mlir"
  ${mlirOpt}/bin/mlir-opt "${affineSlice}" \
    --pass-pipeline='builtin.module(func.func(affine-loop-unroll{unroll-factor=8}),lower-affine,canonicalize)' \
    -o "$out/affine-full-unrolled.mlir"
  ${mlirOpt}/bin/mlir-opt "${affineSlice}" \
    --pass-pipeline='builtin.module(func.func(affine-loop-unroll{unroll-full}),lower-affine,canonicalize)' \
    -o "$out/affine-completely-unrolled.mlir"
  ${pkgs.python3}/bin/python3 - "$out" <<'PY'
import json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
def stats(name):
    text = (root / name).read_text()
    return {
        "bytes": len(text),
        "groups": len(re.findall(r"scf\.for", text)),
        "scf_for": len(re.findall(r"scf\.for", text)),
        "scf_parallel": len(re.findall(r"scf\.parallel", text)),
        "linalg_generic": len(re.findall(r"linalg\.generic", text)),
        "mulf": len(re.findall(r"arith\.mulf", text)),
    }
result = {
    "baseline": stats("baseline.mlir"),
    "specialized": stats("specialized.mlir"),
    "parallel": stats("parallel.mlir"),
    "parallel_loops": stats("parallel-loops.mlir"),
    "affine_parallel": stats("affine-parallel.mlir"),
    "affine_unrolled": stats("affine-unrolled.mlir"),
    "affine_full_unrolled": stats("affine-full-unrolled.mlir"),
    "affine_completely_unrolled": stats("affine-completely-unrolled.mlir"),
}
(root / "stats.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
PY
''
