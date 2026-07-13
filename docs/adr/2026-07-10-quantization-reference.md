# ADR: Use PT2E W8A8 as the primary quantization reference

- Status: accepted
- Date: 2026-07-10

## Context

Task 6 needs a defensible quantization reference before comparing compiler and
hardware-lowering strategies. The local survey of FPGA LLM systems finds
W8A8 is a defensible and common LLM quantization target. W4A8 is relevant but
less consistently documented as a complete deployable
integer-kernel contract. AWQ provides a strong W4 weight artifact, but surveyed
FPGA uses may dequantize weights to FP32 before multiplication.

The existing PT2E W4A8 experiment accepts the requested ranges but leaves
float linear and matmul operations surrounded by quantize/dequantize nodes. A
bit-width label is therefore not sufficient evidence of integer hardware
compute.

## Decision

Use standard PT2E W8A8 as the primary Task 6 numerical reference. The selected
PT2E quantizer, calibration inputs, converted graph, and output behavior are
frozen and used as the oracle for candidate hardware paths. SmoothQuant W8A8
is a separate later variant, not an assumption built into the primary
reference. W4A8/AWQ-style paths are secondary hypotheses and must be labeled
explicitly as weight compression unless integer MAC equivalence is
demonstrated.

The quantization reference must specify packed values, scales, zero-points,
axis or group size, signedness, accumulator width, and requantization rules. A
CPU oracle must consume the same artifact contract as the eventual hardware
path.

Quantization reference, representation lowering, and backend selection remain
separate claims:

1. the reference defines the numerical result;
2. a rewrite or quantizer determines whether compute is genuinely integer or
   fixed-point;
3. Torch-MLIR/TOSA/CIRCT or common reusable kernels implement that form.

## Initial operator scope

The first W8A8 contract quantizes linear/GEMM operations, including Q/K/V and
MLP projections, with int8 activations, int8 weights, int32 accumulation, and
explicit requantization at kernel boundaries. LayerNorm, softmax, and
GELU/activation approximations remain FP32 initially and are measured as
separate later claims. Every Q/DQ boundary is explicit.

PT2E calibration uses a fixed, versioned full-TinyStories corpus rather than
random RC inputs. Token IDs, sequence lengths, calibration outputs, and their
hashes are recorded and reused for every quantization/compiler comparison. RC
calibration is permitted for debugging only, not as the primary FTS claim.

The initial granularity is symmetric int8 weights per output channel and
symmetric int8 activations per operator/tensor using frozen calibration
scales. Accumulation is int32, with explicit per-output-channel
requantization. Per-token and per-group activation scales are deferred as
separate experiments.

Before compiler lowering, validate the quantized reference independently. Emit
the exact packed int8 weights, activation scales, zero-points, accumulator and
requantization metadata, then run a CPU integer oracle over those same packed
artifacts. Compare against FP32 PyTorch before passing any quantized graph or
component to Torch-MLIR.

SmoothQuant scale migration is deferred. If introduced, it becomes an explicit
variant applied before `torch.export`, with its alpha and scale artifact
recorded separately.

The canonical reference implementation is the existing static symmetric
`XNNPACKQuantizer` PT2E configuration with W8A8 ranges. Its calibration inputs,
converted graph, output vectors, and graph-shape audit are frozen as the
reference artifacts, even if the converted graph retains Q/DQ-wrapped float
operations.

After the reference is frozen, the first transformation targets one contiguous
region discovered from the real full-TinyStories exported FX/ATen graph. The
region must be wrapped as a standalone reference component, lowered through a
candidate path, compared against the frozen PT2E W8A8 output, and measured for
float-compute removal and resource effect.

A candidate lowering succeeds structurally only if it matches the PT2E W8A8
reference at the component boundary, retains explicit integer or fixed-point
compute in the target GEMM/linear region, removes unintended FP32 linear or
matmul operations there, and emits a measurable RTLIL, SV, or common-kernel
artifact. FP32 outside the target region is permitted for the first experiment.

## First milestone

1. Build the canonical XNNPACK PT2E W8A8 reference.
2. Freeze calibration data, the converted graph, output vectors, and metadata.
3. Run the existing graph-shape audit.
4. Report where compute remains float.
5. Only then attempt Torch-MLIR, TOSA, FX, or ExecuTorch transformations
   against that reference.

This milestone establishes a numerical oracle and distinguishes a viable
compiler input from a useful simulation reference.

## Immediate full-model experiment

Before building graph-derived component extraction, run the full TinyStories
model through the obvious quantized compiler path:

```text
Full TinyStories -> PT2E W8A8 -> TOSA -> no-handshake lowering -> RTLIL
```

Keep the checkpoint, memory blackboxing/externalization, wrapper, and toolchain
fixed relative to the raw-FP32 baseline. Initially stop at RTLIL/Yosys
statistics and record graph shape, compiler time, artifact size, and LUT/FF/
BRAM/DSP deltas. Require quantized-path functional equivalence before treating
resource results as valid. SmoothQuant remains the next controlled variant if
the PT2E route is still Q/DQ-wrapped float compute.

This full-model experiment precedes graph-derived component extraction. The
component framework remains the diagnosis and fast-iteration fallback if the
full quantized path fails or remains too large.

The integer CPU oracle must be bit-exact against the packed-artifact
implementation. Comparison against FP32 reports maximum and mean absolute
error, RMSE, and next-token top-1 agreement over every frozen evaluation
prompt. Component numerical tolerance and full-model task-level agreement are
separate gates.

For the immediate full-model scout, defer equivalence, board validation, and
simulation. Still generate SV and run Yosys statistics. These are provisional
resource results until functional equivalence is added; preserve the PT2E
reference graph and outputs so later equivalence uses the same experiment.

Reuse the existing PT2E implementation from `~/LLM2FPGA` as the starting
point: port the XNNPACKQuantizer adapter, calibration flow, and graph-shape
audit into the active repository, changing only package wiring and the current
TOSA/no-handshake pipeline integration. Preserve the source implementation as
provenance and do not introduce a new quantization algorithm during the scout.
