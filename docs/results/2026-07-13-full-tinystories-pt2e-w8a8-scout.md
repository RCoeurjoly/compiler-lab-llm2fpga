# Full TinyStories PT2E W8A8 scout

Date: 2026-07-13

## Outcome

The first full-model PT2E W8A8 scout reached TOSA but did not reach Linalg, SystemVerilog, or Yosys. TOSA-to-Linalg rejects PT2E-generated integer residual additions because the TOSA profile does not permit `i8 + i8 -> i8` for `tosa.add`:

```text
'tosa.add' op illegal: operation operand/result data types did not align with
any profile or extension, got (i8,i8,i8), did you mean (i32,i32,i32)?
```

This is a useful negative result: applying standard XNNPACK PT2E W8A8, TOSA, and no-handshake lowering is not by itself a path to synthesizable integer hardware in the current pipeline. No SV was generated and no Yosys resource statistics exist for this scout.

## Configuration

- Model: full TinyStories checkpoint and architecture already used by the repository.
- Quantizer: XNNPACK PT2E static W8A8.
- Calibration: the adapter's frozen single-token zero input.
- Compiler route: PyTorch export -> Torch-MLIR -> TOSA -> Linalg -> SCF -> flat SCF -> Calyx -> HW -> SV -> Yosys.
- Handshake lowering: omitted by selecting the existing no-handshake route.
- Equivalence, board validation, and SmoothQuant: deliberately deferred.

The calibration is reproducible but is only a scout calibration, not a representative quality calibration. This result must therefore not be interpreted as a validated W8A8 accuracy result.

## Graph-shape audit

The post-PT2E exported graph is QDQ-heavy and still float-facing at important compute operations:

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

The audit therefore fails all four structural checks: float matmul, float linear, float layer norm, and GELU/tanh-style float math remain. PT2E W8A8 is currently suitable as a numerical reference and graph-transformation input, but not as proof that the compiler is receiving an integer-only model.

## Build frontier and provisional measurements

Command:

```sh
scripts/pipeline/monitor_build.sh /tmp/full-tinystories-w8a8-scout 5 -- \
  nix build .#tinystories-w8a8-via-tosa-no-handshake-yosys-stat \
  --no-link --print-out-paths -L
```

| Measurement | Result |
|---|---:|
| Exit status | 1 |
| Last successful stage | TOSA |
| Failed stage | TOSA-to-Linalg |
| Monitored wall time | 15 s |
| Peak sampled VM RSS | 565,472 KiB |
| Torch MLIR | 3,025 lines; 27,233,314 bytes |
| TOSA MLIR | 6,155 lines; 27,430,773 bytes |
| SV generated | No |
| Yosys statistics | Not reached |

The timing is not a cold end-to-end compiler measurement because successful upstream Nix derivations were cached. It is retained only as provisional execution evidence.

Torch-MLIR emitted 24 warnings that quantized operands were only partially traced and that the affected operations would remain in QDQ form. TOSA generation nevertheless completed. TOSA-to-Linalg then reported the illegal `i8` additions repeatedly, including activation shapes `tensor<1x1x64xi8>`, `tensor<1x1x256xi8>`, and the output-head shape `tensor<1x1x50257xi8>`.

## Interpretation and next decision

The obvious full-model path has now been tested before investing in equivalence infrastructure. It exposes two separate issues:

1. The PT2E graph leaves major compute surrounded by quantize/dequantize boundaries and float operations.
2. The integer operations that do survive cannot all be legalized by the current TOSA profile and TOSA-to-Linalg route.

The next compiler experiment should be narrow and measurable: isolate one extracted residual-add/linear fragment from this actual PT2E/Torch-MLIR output and decide where requantization and accumulator widening belong. In particular, test an `i32` accumulator/add followed by explicit requantization to `i8`, then apply the proven rewrite to the full graph. This keeps the full PT2E graph as the canonical source and avoids inventing an ad hoc model component.

Machine-readable evidence is in [`artifacts/full-tinystories-pt2e-w8a8-scout/result.json`](../../artifacts/full-tinystories-pt2e-w8a8-scout/result.json).
