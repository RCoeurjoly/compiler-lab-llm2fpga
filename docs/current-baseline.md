# Current Baseline

## Representative-core W4A8, TOSA no-handshake Calyx-SV

Recorded on 2026-07-08.

- Repository commit: `f02fdee3132071d31ef9a1b9d64ff09b98ab0765`
- Worktree before baseline build: clean
- Target package: `tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx-sv`
- Baseline command:
  `nix build .#tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx-sv --no-link --print-out-paths -L`
- Companion shorter command:
  `nix build .#tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx --no-link --print-out-paths -L`

## Pipeline

The intended active pipeline is:

1. PyTorch representative-core W4A8 exported program
2. `torch-mlir`
3. TOSA
4. TOSA-to-Linalg
5. SCF
6. Flat SCF
7. Calyx
8. Calyx-SV

This is the baseline to debug from for the resource-minimization work. It is
not yet a resource result for the board, because the current run fails before
Calyx or SystemVerilog generation.

## Outcome

- Status: failed
- Last known good stage: TOSA
- First failing stage: TOSA-to-Linalg
- Failing derivation:
  `/nix/store/s6zcbra5n806px73igjck314gfrkx6bd-tinystories-representative-core-w4a8-linalg.mlir.drv`
- Failing input artifact reported by the build:
  `/nix/store/29h9i8j4hv93chiyjd6jgz1mzny3nfgh-tinystories-representative-core-w4a8-tosa.mlir`

The TOSA-to-Linalg stage rejects many quantized `tosa.add` operations with
`i8` operands and `i8` results. The first reported failure was:

```mlir
%187 = tosa.add %186, %45 : (tensor<1x1x2xi8>, tensor<1x1x1xi8>) -> tensor<1x1x2xi8>
```

The verifier message says the operand/result data types do not align with a
supported TOSA profile or extension and suggests the supported add profile is
`i32, i32, i32`.

## Warnings Before The Failure

The PyTorch export stage reaches an exported program, but reports that
`torch.export.export_for_training` is deprecated.

The Torch MLIR stage reaches MLIR, but PyTorch warns about non-writable buffers
while loading state.

The TOSA stage succeeds, but warns:

```text
Partially traced quantized operands. This op will remain in QDQ form.
```

Those warnings appear around quantized `torch.aten.matmul` sites.

## Interpretation

This baseline is a compiler-legality blocker, not yet a hardware-resource
measurement. Clean upstream torch-mlir plus the current representative-core W4A8
adapter can emit TOSA, but the emitted TOSA is not legal for the current
TOSA-to-Linalg lowering because quantized additions remain as `i8` `tosa.add`.

No textual MLIR rewrite is allowed as the fix. Acceptable fix classes are:

- Defensible PyTorch quantization or model expression changes that preserve an
  equivalence-testing story.
- Upstream/tool-supported TOSA legalization.
- A real MLIR/CIRCT pass, if the transformation belongs in the compiler
  pipeline and can be tested as such.

## Next Debug Steps

1. Preserve this baseline as the known starting point for task 6.
2. Minimize the failing `i8` `tosa.add` pattern from the TOSA artifact.
3. Decide whether the correction belongs in PyTorch quantization, TOSA
   legalization, or a dedicated MLIR pass.
4. Add a diagnostic or failing test that catches illegal quantized `tosa.add`
   before the long Calyx-SV build.
5. After the legality blocker is fixed, rerun the same Calyx-SV package and
   record the next baseline.

## Direct-Linalg No-Handshake Follow-Up

The TOSA failure is avoided by changing frontend dialects, not by rewriting
MLIR text. The direct torch-to-Linalg no-handshake variant is exposed as:

```text
tinystories-representative-core-w4a8-via-linalg-no-handshake
```

The `linalg` and `scf` stages build for this variant. The current first failing
stage moves later to `flat-scf`:

```text
failed to legalize unresolved materialization from ('memref<2xf32>') to ('memref<1x1x2xf32>')
```

The reported live user is a `memref.expand_shape` from `memref<1x1x2xf32>` into
`memref<1x1x1x2xf32>`. This is the next compiler-pipeline blocker to debug if
the direct-Linalg dialect route becomes the active path.
