# ADR: Qualify a quantized representative core at the Torch-MLIR boundary

- Status: accepted
- Date: 2026-07-16

## Context

The previous reduced TinyStories cores are useful compiler experiments, but
they are not valid representatives of the quantized full model: some replace
native embedding, attention, normalization, or activation behavior with
hardware-oriented implementations. Their small size therefore does not show
that a change will survive the same lowering constructs as full TinyStories.

The project needs a faster way to diagnose compiler changes without silently
changing the input model. The first useful boundary is Torch-MLIR, before
TOSA, RTLIL, SV, or FPGA mapping. It is cheap enough to sweep configurations
and exposes the native PT2E W8A8 graph that downstream lowering receives.

## Decision

Use the following definition for the PT2E W8A8 representative-core study.

- The full reference is the pretrained TinyStories-1M GPT-Neo configuration,
  exported with static XNNPACK PT2E W8A8 quantization.
- A reduced candidate is constructed only with
  `AutoModelForCausalLM.from_config`. It may scale vocabulary, layers,
  position table, local-attention window, hidden width, and head count, but
  must not replace native GPT-Neo modules.
- Both sides use the checked-in eight-token structural input. The reduced
  vocabulary maps the six token-equality classes in that input without
  changing repetition, ordering, or positions. This is structural calibration,
  not a language-quality corpus or an accuracy claim.
- Qualification is mechanically derived from the resulting Torch-MLIR. A
  candidate must include every full-model operation name, normalized operation
  signature, and producer-to-consumer operation edge.
- An **iteration surrogate** additionally needs at least 10x end-to-end
  Torch-MLIR lowering speed and serialized MLIR at most 0.10x the full model.
  A 100x speedup is the operational target.
- When no candidate meets the speed gate, the study reports a **structural
  finalist** instead: the coverage-complete candidate with the smallest
  serialized Torch-MLIR. This is not relabeled as an iteration surrogate.

The reproducible study target is:

```sh
nix build .#tinystories-w8a8-rc-study -L --no-link --print-out-paths
```

It records fingerprints, phase timings, artifact identity, every candidate
qualification, and a deterministic summary in one Nix output.

## Result of the initial PT2E W8A8 study

The structural finalist is
`tinystories-w8a8-rc-study-mask9-vocab6-width2`:

| Field | Full PT2E W8A8 | Structural finalist |
| --- | ---: | ---: |
| Vocabulary | 50,257 | 6 |
| Layers | 8 | 2 |
| Position table | 2,048 | 9 |
| Local window | 256 | 256 |
| Hidden width | 64 | 2 |
| Heads | 16 | 1 |
| Input | `[1, 8]` `int64` | `[1, 8]` `int64` |

The eight-position table folds away the boolean causal-mask slice/`where`
path. A position table of nine preserves it. Width one folds away a required
LayerNorm `broadcast_to` path; width two preserves it. A window of one also
has complete structural coverage, but produces 20 more serialized MLIR bytes;
the finalist keeps the full-model window and is marginally smaller.

The finalist is approximately 249x smaller in serialized Torch-MLIR, but its
end-to-end lowering is only 1.586x faster and its Torch-MLIR import phase is
only 3.011x faster. It therefore fails the 10x speed gate. The result is a
useful structure-preserving core for downstream A/B diagnosis, not the
orders-of-magnitude iteration loop originally sought.

## Consequences

The old W4A8 RCs remain historical hardware experiments and must not be used
as this study's baseline or be described as clean quantized representatives.

This decision makes no functional-equivalence, quantized-accuracy, integer
compute, TOSA, RTLIL, SV, LUT/FF/BRAM/DSP, DDR3, board, or latency claim. The
project's canonical full frozen PT2E W8A8 reference remains the numerical
oracle; this eight-token full export is its structural compiler baseline.
SmoothQuant is a later controlled profile that must reuse this input,
fingerprint, timing, and qualification interface rather than changing the
definition of representativeness.
