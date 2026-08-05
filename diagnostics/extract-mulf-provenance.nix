{ pkgs
, preCalyx
, futil
}:

pkgs.runCommand "tinystories-w8a8-mulf-provenance" {
  nativeBuildInputs = [ pkgs.python3 ];
} ''
  mkdir -p "$out"
  ${pkgs.python3}/bin/python3 ${../scripts/pipeline/extract_mulf_provenance.py} \
    --mlir ${preCalyx}/pre-calyx.mlir \
    --futil ${futil}/model.futil \
    --out "$out/provenance.json" \
    --slice-out "$out/slice.mlir" \
    --parallel-slice-out "$out/parallel-slice.mlir" \
    --affine-slice-out "$out/affine-slice.mlir"
''
