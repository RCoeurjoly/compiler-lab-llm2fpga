# Full TinyStories PT2E W8A8 scout

Date: 2026-07-13

## Outcome

The full TinyStories PT2E W8A8 no-handshake scout now lowers all the way through
TOSA, Linalg, SCF, Calyx, Futil, and SystemVerilog. `yosys-slang` accepts the
74,132,122-byte generated design with zero errors and zero warnings and reports
5,938,460 structural cells. The top is `main` with only `clk`, `reset`, `go`,
and `done` ports.

This is a successful **structural frontend utilization** measurement before
Yosys process expansion. It is not technology-mapped FPGA utilization such as
LUT/FF/BRAM counts.
An attempted deeper `proc; opt; memory; opt_clean` run was killed for memory
after reaching approximately 25.4 GiB, so no FPGA-family utilization claim is
made.

The former TOSA-to-Linalg blocker was PT2E quantization zero-point scaffolding, not transformer residual addition. A local compiler pass rewrites the generated narrow arithmetic:

```text
f32 -> i8 cast -> i8 zero-point add
```

into profile-valid, saturating arithmetic:

```text
f32 -> i32 cast -> i32 zero-point add -> identity tosa.rescale -> i8
```

All 236 narrow zero-point additions were rewritten to 236 `tosa.rescale`
operations; no `i8 tosa.add` remains in the validated TOSA. The earlier frontier
was Calyx lowering of the large remaining float/QDQ computation. Exact and
scout-only math legalizations moved past it; an extended whole-model run then
completed. The generated design is intentionally not equivalence-eligible
because the scout approximates `pow`, `exp`, and `tanh`.

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

## Initial failing build frontier

Before the math continuation, the first monitored attempt stopped at the
following frontier. These values are retained as historical diagnostic evidence,
not as the final pipeline status.

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

## Initial Calyx float frontier

The initial diagnostic Calyx package reported `status: failed` because
`lower-scf-to-calyx` did not produce an artifact before legalization. Its
normalized flat-SCF input contains 5,922 float operations:

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

The diagnostic classifier marked 17 `math.rsqrt` operations as unsupported. The
initial Calyx construction attempt failed earlier on `math.floor` and also
reported an unused `init_for_100_induction_var` group. This confirms that standard
PT2E W8A8 plus TOSA legality does not remove the float quantization scaffolding or
nonlinear model math.

## Interpretation and next decision

The narrow TOSA legality problem is fixed. It should no longer be treated as the
resource-scout blocker. PT2E still leaves thousands of float/QDQ operations;
Calyx reaches SV only after explicit math legalization and deliberately rough
nonlinear approximations. That is useful for resource scouting but does not make
the graph integer-only or numerically validated.

The next useful experiment should target the float frontier rather than another generic TOSA legality rewrite. Extract one actual PT2E quantize/dequantize fragment containing `floor`, `ceil`, comparisons, and casts, then determine whether it should be replaced by integer `tosa.rescale` earlier in Torch-to-TOSA. Separately, layer normalization and nonlinear operations account for `rsqrt`, `pow`, `exp`, and `tanh`; those require explicit hardware-oriented integer approximations or externalized implementations.

## Calyx continuation and iteration cutoff

A follow-up resource-only run lowered `floor`, `ceil`, and `rsqrt` exactly into
SCF-to-Calyx-supported arithmetic. For this named full-model scout only, it also
used explicit provisional approximations for the remaining nonlinear operations:
`pow(x, 3)` became two multiplies, `exp(x)` became `1 + x`, and `tanh(x)` became
`clamp(x, -1, 1)`. These approximations are not part of the PT2E numerical
reference and cannot support an equivalence claim.

This removed the immediate unsupported-operation failure. A first run was stopped
at the former 40-minute resource-scout cutoff, but that cutoff proved to be an
iteration policy rather than a compiler failure. The user reran the public
`tinystories-w8a8-via-tosa-no-handshake-calyx` target without that short cutoff;
it completed and emitted a 36,139,994-byte Calyx MLIR artifact.

The export path removed one provably unreferenced private `memref.global`, encoded
CIRCT decimal f32 constants as exact IEEE-754 `std_const` bit patterns for the
available Calyx parser, and used the upstream Calyx float library plus HardFloat.
Native Calyx needed an unlimited process stack and approximately 31 minutes. It
emitted 18,613,321 bytes of Futil and 74,132,122 bytes of SystemVerilog.

## `yosys-slang` structural utilization and liveness

Every SystemVerilog source, including HardFloat, was read through the
`yosys-slang` plugin. The Yosys native SystemVerilog frontend was not used. The
frontend command used `--no-proc`; Yosys then ran only hierarchy assertions and
`stat -json`.

| Measurement | Result |
|---|---:|
| Frontend result | 0 errors; 0 warnings |
| Top | `main` |
| Top ports | `clk`, `reset`, `go`, `done` |
| Frontend/stat wall time | 2,851.57 s |
| `read_slang` time | 2,837 s |
| Peak memory | 25,400.48 MB |
| Wires / wire bits | 5,739,631 / 57,641,597 |
| Public wires / bits | 2,385,417 / 16,736,975 |
| Processes | 46,982 |
| Structural cells | 5,938,460 |
| Memories / memory bits | 10,199 / 236,744,916 |
| `$dff` / `$aldff` | 61,547 / 42 |
| `$mul` | 1,147 |
| `$add` / `$sub` | 51,647 / 11,941 |
| `$mux` | 708,653 |

The liveness guard asserted exactly one `main` module and exactly one `done` wire,
then attached `keep=1` to `main/done` and asserted exactly one kept object. The
ordinary and output-kept structural JSON reports are byte-identical (SHA-256
`1104fb8cca35d8e1b706962ffb6af8691c6ab772e44c73efabf6b8945b6215fd`). Thus
keeping the observable completion output does not alter the reported structural
design at this boundary.

This is a structural liveness check, not proof that simulation eventually raises
`done`; functional equivalence and temporal liveness remain deferred as agreed.

A separate attempt to run `proc; opt; memory; opt_clean` reached roughly 25.4 GiB
resident memory and was killed with exit status 137. Therefore the table is not
technology-mapped FPGA utilization and must not be compared directly with LUT,
FF, DSP, or BRAM device capacities. The immediate quantitative conclusion is
nevertheless clear: the present full-model Calyx scout is enormous, contains
236,744,916 structural memory bits, and is not a fast whole-model iteration loop.
Component-level experiments remain necessary.

Machine-readable evidence is in
[`result.json`](../../artifacts/full-tinystories-pt2e-w8a8-scout/result.json) and
[`yosys-slang-structural-utilization.json`](../../artifacts/full-tinystories-pt2e-w8a8-scout/yosys-slang-structural-utilization.json).
