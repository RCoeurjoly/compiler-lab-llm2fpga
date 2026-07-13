# Full TinyStories PT2E W8A8 scout

Date: 2026-07-13

## Outcome

The full TinyStories PT2E W8A8 no-handshake scout now passes TOSA validation and lowers through Linalg, SCF, and flat-SCF. It does not yet generate Calyx or SystemVerilog, so Yosys resource statistics remain unavailable.

The former TOSA-to-Linalg blocker was PT2E quantization zero-point scaffolding, not transformer residual addition. A local compiler pass rewrites the generated narrow arithmetic:

```text
f32 -> i8 cast -> i8 zero-point add
```

into profile-valid, saturating arithmetic:

```text
f32 -> i32 cast -> i32 zero-point add -> identity tosa.rescale -> i8
```

All 236 narrow zero-point additions were rewritten to 236 `tosa.rescale` operations; no `i8 tosa.add` remains in the validated TOSA. The next frontier is Calyx lowering of the large remaining float/QDQ computation. The first runtime rejection is `math.floor`, followed by an unused generated Calyx group.

## Configuration

- Model: full TinyStories checkpoint and architecture already used by the repository.
- Quantizer: XNNPACK PT2E static W8A8.
- Calibration: the adapter's frozen single-token zero input.
- Compiler route: PyTorch export -> Torch-MLIR -> raw TOSA -> legalized and validated TOSA -> Linalg -> SCF -> flat-SCF -> Calyx -> SV -> Yosys.
- Handshake lowering: omitted by selecting the existing no-handshake route.
- Equivalence, board validation, and SmoothQuant: deliberately deferred.

The calibration is reproducible but is only a scout calibration, not a representative quality calibration. This result must not be interpreted as a validated W8A8 accuracy result.

## Legalization safety boundary

The pass `llm2fpga-legalize-pt2e-tosa-zero-point` matches producer provenance, not consumers:

- The result and both operands are ranked `i8` tensors.
- One operand is produced by a cast from a float tensor.
- The other operand is a broadcastable splat `i8` constant representing the zero point.

The pass does not require one use or an immediate `i8 -> i32` cast. Quantized values may feed dequantization, reshape, integer matmul, or several consumers without changing their production semantics. A negative regression proves that an unrelated `i8 + i8` remains unchanged and is still rejected by `tosa-validate`.

The TOSA boundary uses a pass plugin compiled against the same MLIR 23 ABI as the Torch-MLIR TOSA consumer. The existing MLIR 21 plugin remains separate for downstream pipeline utilities; loading it into MLIR 23 was reproduced as an invalid cross-ABI configuration and removed.

## Graph-shape audit

The post-PT2E exported graph remains QDQ-heavy and float-facing at important compute operations:

| Operation family | Count |
|---|---:|
| `quantized_decomposed.dequantize_per_tensor` | 374 |
| `quantized_decomposed.quantize_per_tensor` | 246 |
| `aten.linear` after dequantization | 49 |
| `aten.matmul` after dequantization | 16 |
| `aten.layer_norm` | 17 |
| `aten.pow` | 8 |
| `aten.tanh` | 8 |
| `aten.softmax` | 8 |

PT2E W8A8 is therefore still a numerical reference and graph-transformation input, not an integer-only hardware model.

## Build frontier and provisional measurements

Command:

```sh
scripts/pipeline/monitor_build.sh \
  /tmp/full-tinystories-w8a8-consumer-independent-scout 5 -- \
  nix build .#tinystories-w8a8-via-tosa-no-handshake-yosys-stat \
  --no-link --print-out-paths -L
```

| Measurement | Result |
|---|---:|
| Exit status | 1 |
| Last successful IR stage | flat-SCF |
| Failed stage | Calyx lowering/handoff |
| First rejected operation | `math.floor` |
| Monitored wall time | 363 s |
| Peak sampled VM RSS | 565,228 KiB |
| Torch MLIR | 3,025 lines; 27,233,314 bytes |
| Raw TOSA MLIR | 6,155 lines; 27,430,773 bytes |
| Validated TOSA MLIR | 6,311 lines; 27,488,188 bytes |
| Linalg MLIR | 30,019 lines; 28,911,438 bytes |
| SCF MLIR | 38,806 lines; 28,939,165 bytes |
| Flat-SCF MLIR | 29,192,575 bytes |
| Calyx generated | No |
| SV generated | No |
| Yosys statistics | Not reached |

Torch and raw TOSA were cached. The monitored run built the ABI-matched plugin and the Linalg-through-Calyx frontier, so 363 seconds is not a cold end-to-end measurement.

## Calyx float frontier

The diagnostic Calyx package reports `status: failed`: `lower-scf-to-calyx` did not produce a Calyx artifact. Its normalized flat-SCF input contains 5,922 float operations:

| Operation | Count |
|---|---:|
| `arith.cmpf` | 2,148 |
| `arith.mulf` | 1,129 |
| `arith.sitofp` | 757 |
| `arith.subf` | 503 |
| `arith.fptosi` | 478 |
| `math.floor` | 478 |
| `math.ceil` | 239 |
| `arith.addf` | 141 |
| `math.rsqrt` | 17 |
| `arith.divf` | 8 |
| `math.exp` | 8 |
| `math.powf` | 8 |
| `math.tanh` | 8 |

The diagnostic classifier marks 17 `math.rsqrt` operations as unsupported. The actual Calyx construction attempt fails earlier on `math.floor` and also reports an unused `init_for_100_induction_var` group. This confirms that standard PT2E W8A8 plus TOSA legality does not remove the float quantization scaffolding or nonlinear model math.

## Interpretation and next decision

The narrow TOSA legality problem is fixed. It should no longer be treated as the resource-scout blocker. The dominant problem has moved to the expected higher-level issue: PT2E leaves thousands of float/QDQ operations, and Calyx cannot lower that computation directly.

The next useful experiment should target the float frontier rather than another generic TOSA legality rewrite. Extract one actual PT2E quantize/dequantize fragment containing `floor`, `ceil`, comparisons, and casts, then determine whether it should be replaced by integer `tosa.rescale` earlier in Torch-to-TOSA. Separately, layer normalization and nonlinear operations account for `rsqrt`, `pow`, `exp`, and `tanh`; those require explicit hardware-oriented integer approximations or externalized implementations.

Machine-readable evidence is in [`artifacts/full-tinystories-pt2e-w8a8-scout/result.json`](../../artifacts/full-tinystories-pt2e-w8a8-scout/result.json).
