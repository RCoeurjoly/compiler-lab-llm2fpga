# Full TinyStories W8A8 Direct-Linalg No-Handshake Scout

## Result

**Frontier:** the frozen full TinyStories PT2E W8A8 graph now crosses the
previous `arith.uitofp i1 -> f32` Calyx boundary. Its normalized pre-Calyx
input has a clean census for that conversion and the selected residual memref
forms. CIRCT instead stops at eight `math.fpowi` operations, all with a
constant integer exponent of three.

This is a real full-model result for the deliberately non-TOSA route:

```text
PyTorch ExportedProgram -> Torch-MLIR -> Direct Linalg -> SCF -> flat-SCF -> Calyx
```

It is not yet a Calyx, SystemVerilog, RTLIL, Yosys, technology-mapping, or
XC7K480T-utilization result. The stage stopped before any of those artifacts
could exist.

## Input and route

The [existing `tinystories-w8a8` registration](../../nix/models.nix) supplies:

- the full `roneneldan/TinyStories-1M` checkpoint;
- XNNPACK PT2E static W8A8 export;
- frozen single-token zero-input calibration; and
- exported example input shape `[1, 1]`, `torch.int64`.

The public alias is:

```text
tinystories-w8a8-via-linalg-no-handshake
```

It selects `pipelineStagePackagesNoHandshake` and `noHandshakeLinalgStages`.
There is no TOSA stage in this experiment. It must not be conflated with the
separate explicit-integer representative-core experiment, which is a
micro-slice with literal tensors rather than this checkpoint-backed PT2E
graph.

## Current stage evidence

| Stage | Immutable Nix output | Observation |
|---|---|---|
| Torch MLIR | `/nix/store/hnlj9dv35jg933mlvhn4abzv3lfcxn0m-tinystories-w8a8-torch.mlir` | Completed. |
| Direct Linalg | `/nix/store/rl3zkby142if1wzy6f1663lxx4nslgk2-tinystories-w8a8-linalg.mlir` | Completed. Torch-MLIR still warns that several attention matmuls have partially traced quantized operands and remain QDQ-shaped. |
| SCF | `/nix/store/zbgi6sa7dcg0q3c6w6grz7b1713yhizh-tinystories-w8a8-scf.mlir` | Completed. |
| flat-SCF | `/nix/store/wfrf67k43gvas5fr5v326jh6y3cmnz24-tinystories-w8a8-flat-scf` | `manifest.json` is `completed-with-residuals`. Its raw blocker report records 339 `memref.reinterpret_cast`, 115 `memref.copy`, 43 `memref.expand_shape`, and 13 `memref.collapse_shape` operations. |
| Pre-Calyx legality census | `/nix/store/bsvxck5ij1gkj2csmwjxivk4q5830nnl-tinystories-w8a8-calyx/pre-calyx-legality.json` | `status: ok`; no selected prohibited operations in the normalized input, including no `arith.uitofp`. This narrow census does not assert general Calyx legality. |
| Calyx | `/nix/store/bsvxck5ij1gkj2csmwjxivk4q5830nnl-tinystories-w8a8-calyx` | `manifest.json` is `failed`, with `exit_code: 1`: `lower-scf-to-calyx` did not produce `model.calyx.mlir`. |

The raw flat-SCF residual report and the clean pre-Calyx census describe
different boundaries: the former preserves raw lowering diagnostics; the
latter examines the normalized input actually handed to CIRCT. The latter is
clean only for its deliberately narrow list, not a claim that every operation
is supported.

Reproduce the evaluated boundary with:

```sh
nix build .#tinystories-w8a8-via-linalg-no-handshake-calyx -L --no-link --print-out-paths
```

## Terminal diagnostic

`lower-scf-to-calyx.log` reports its first substantive failure in CIRCT's
`BuildOpGroups()`:

```text
error: Unhandled operation during BuildOpGroups()
%608 = math.fpowi %607, %c3_i64 : f32, i64
```

The normalized pre-Calyx input contains eight such `math.fpowi` operations;
each has `%c3_i64` as its exponent. The later diagnostic about an unused
`calyx.group` is a cascade from this failure, not an independent frontier.

The previous exact `i1 -> f32` problem is not present: the new pre-Calyx
legalization rewrites that form through `i32` before CIRCT sees it. The active
scout-math pass currently recognizes `math.exp`, `math.powf`, and `math.tanh`,
but not `math.fpowi`; that omission explains why this is the next frontier.

`float-frontier.json` reports 4,062 recognized floating-point operations and
zero operations in its narrow unsupported classification. It counts
`math.fpowi` among the recognized math operations but does not classify it as
unsupported. Therefore that zero is a scanner-coverage limitation, not
evidence that Calyx supports `math.fpowi`.

## Downstream status

No `model.calyx.mlir` was generated. Accordingly, native-SV lowering, RTLIL
generation, Yosys statistics, XC7K480T LUT/FF/BRAM/DSP mapping, and
nextpnr-xilinx packing/place/route were intentionally not attempted. There
is no resource-utilization claim for this full-model route.

The existing scout-math replacements are explicitly approximate, so this
experiment also makes no PyTorch-to-SV functional-equivalence claim.

## Next decision

The next bounded investigation is to minimize and classify the eight
constant-exponent `math.fpowi` operations, then decide whether a narrow
constant-exponent legalization is appropriate. It should be designed and
tested separately; this scout does not silently generalize it to arbitrary
integer powers or float operations.
