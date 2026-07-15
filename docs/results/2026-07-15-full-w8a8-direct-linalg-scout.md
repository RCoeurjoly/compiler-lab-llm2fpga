# Full TinyStories W8A8 Direct-Linalg No-Handshake Scout

## Result

**Frontier:** `lower-scf-to-calyx` failed. The actual frozen full TinyStories
PT2E W8A8 export produced Direct-Linalg and SCF artifacts, then a flat-SCF
artifact whose manifest is `blocked`, without a TOSA stage. Calyx lowering
then failed because it cannot legalize `arith.uitofp` from `i1` to `f32`.

The terminal Calyx manifest says that lowering did not produce a Calyx
artifact. This report therefore contains no SystemVerilog, RTLIL, Yosys
statistic, technology-mapping, or XC7K480T-utilization result for this route.

## Input and route

The [existing `tinystories-w8a8` registration](../../nix/models.nix) defines
the input as:

- full `roneneldan/TinyStories-1M` checkpoint;
- XNNPACK PT2E static W8A8 export;
- frozen single-token zero-input calibration;
- exported example input shape `[1, 1]`, `torch.int64`;
- immutable model-registry metadata:
  `/nix/store/rw92gzhvn79sr08kywssh04fm3kazzwd-model-registry.json`;
- immutable exported-program output:
  `/nix/store/z7jmd8998f0xbz6qy3gcmx9r2s616m0h-tinystories-w8a8-pytorch-exported`.

The [new public alias](../../flake.nix) is:

```text
tinystories-w8a8-via-linalg-no-handshake
```

Its route is deliberately:

```text
PyTorch ExportedProgram → Torch-MLIR → Direct Linalg → SCF → flat-SCF → Calyx
```

It uses `pipelineStagePackagesNoHandshake` and `noHandshakeLinalgStages`; the
[alias and stage list](../../flake.nix) contain no TOSA stage or TOSA pipeline
package. The immutable active-variant record is:

```text
/nix/store/bz5h2f6ndv3bsibka07kcl8ybxgssi6z-active-pipeline-variants.json
```

## Completed stages

| Stage | Immutable Nix output | Observation |
|---|---|---|
| Torch MLIR | `/nix/store/hnlj9dv35jg933mlvhn4abzv3lfcxn0m-tinystories-w8a8-torch.mlir` | Completed. |
| Direct Linalg | `/nix/store/dq4smgfzgi03kpnq10dklzmw6iam3bsx-tinystories-w8a8-linalg.mlir` | Completed, with Torch-MLIR warnings that several attention matmuls have partially traced quantized operands and remain QDQ-shaped. |
| SCF | `/nix/store/am3cz1bh69ahp4xn8n5y7vksjilb7qq3-tinystories-w8a8-scf.mlir` | Completed. |
| flat-SCF | `/nix/store/1pnjvyyzm4249rk7qs8gwimn9nk4k9pb-tinystories-w8a8-flat-scf` | Artifact produced, but `manifest.json` has `status: blocked`; its diagnostic reports 339 `memref.reinterpret_cast`, 115 `memref.copy`, 43 `memref.expand_shape`, and 13 `memref.collapse_shape`. |
| Calyx | `/nix/store/c7slna7w1vw6bhvsdn505w001igsl17x-tinystories-w8a8-calyx` | Frontier; its manifest records `status: failed`, `exit_code: 1`, and reason `lower-scf-to-calyx did not produce a Calyx artifact`. |

Reproduction commands:

```sh
nix build .#tinystories-w8a8-via-linalg-no-handshake-torch -L --no-link
nix build .#tinystories-w8a8-via-linalg-no-handshake-linalg -L --no-link --print-out-paths
nix build .#tinystories-w8a8-via-linalg-no-handshake-scf -L --no-link --print-out-paths
nix build .#tinystories-w8a8-via-linalg-no-handshake-flat-scf -L --no-link --print-out-paths
nix build .#tinystories-w8a8-via-linalg-no-handshake-calyx -L --no-link --print-out-paths
```

## Terminal diagnostic

The Calyx-stage `lower-scf-to-calyx.log` reports:

```text
error: failed to legalize operation 'arith.uitofp' that was explicitly marked
illegal: ... (i1) -> f32
```

Its accompanying float-frontier scanner counted 4,061 recognized floating-point
operations and zero operations in its narrow unsupported-operation
classification. That scanner does not recognize `arith.uitofp`; the input
nevertheless contains the failing `i1`-to-`f32` conversion. The count is
therefore not a complete float/conversion frontier. The immediate failure is
an integer-to-float legalization gap at the Calyx boundary, rather than a TOSA
failure; its absence from the unsupported-math classification does not imply
that the conversion is supported.

Native-SV lowering was not attempted because `lower-scf-to-calyx` did not
produce a Calyx artifact.

The existing [pre-Calyx resource-scout pass](../../nix/pipeline.nix),
`llm2fpga-lower-scout-math-for-calyx`, remains active for
`tinystories-w8a8`. Its [implementation](../../tools/mlir-passes/FoldConstantTruncFOps.cpp)
uses explicitly approximate `pow`, `exp`, and `tanh` replacements. This scout
is consequently not an equivalence result even before the terminal
legalization failure.

## Interpretation

This is the first full-model Direct-Linalg/no-handshake result. It proves that
the full frozen PT2E W8A8 input can reach flat-SCF without TOSA. It does not
support a resource-utilization claim yet.

In particular, it must not be compared numerically with the successful
`tinystories-representative-core-w4a8-integer-via-linalg-no-handshake`
XC7K480T run. That earlier result is an explicit-integer micro-slice with
literal tensors, not this full checkpoint-backed PT2E W8A8 graph.
