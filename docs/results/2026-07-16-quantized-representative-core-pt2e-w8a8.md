# Quantized TinyStories representative-core study: PT2E W8A8

Date: 2026-07-16

## Outcome

We found a clean, structure-complete PT2E W8A8 TinyStories representative
core at the Torch-MLIR boundary:
`tinystories-w8a8-rc-study-mask9-vocab6-width2`.

It is a **structural finalist**, not an iteration surrogate. It retains every
operation name, normalized operation signature, and producer-to-consumer
operation edge found in the full model's measured Torch-MLIR fingerprint. It
does not meet the predeclared 10x lowering-speed gate, so the study correctly
selects no eligible fast-iteration RC.

This is a Torch-MLIR-only result, not an FPGA resource or equivalence result.

## Reproduction and evidence

Command:

```sh
nix build .#tinystories-w8a8-rc-study -L --no-link --print-out-paths
```

The measured result bundle is
`/nix/store/04iqhbwlgpf1fq9zr82m59sbr1knkg9i-tinystories-w8a8-rc-study`.
The full stage is
`/nix/store/5sffm7j7zggi9a2g2k0sx0x7f46pc67n-tinystories-w8a8-rc-study-full-torch-mlir-study`.
The finalist stage is
`/nix/store/c7xibbw2vwjby6nwr8l1h06warnn29id-tinystories-w8a8-rc-study-mask9-vocab6-width2-torch-mlir-study`.

The generated summary reports
`coverage-valid-finalist-without-speed-eligibility`; its
`selected_candidate` is `null` and its `structural_finalist` is
`mask9-vocab6-width2`. A durable transcription of the generated evidence is
[`result.json`](../../artifacts/quantized-representative-core-pt2e-w8a8/result.json).

## Configuration

| Parameter | Full PT2E W8A8 | Finalist |
| --- | ---: | ---: |
| Vocabulary | 50,257 | 6 |
| Layers | 8 | 2 |
| Maximum positions | 2,048 | 9 |
| Local-attention window | 256 | 256 |
| Hidden width | 64 | 2 |
| Heads | 16 | 1 |
| Frozen input | `[1, 8]` `int64` | `[1, 8]` `int64` |

The core is a native GPT-Neo configuration made with
`AutoModelForCausalLM.from_config`; it contains no custom embedding,
attention, LayerNorm, GELU, or residual replacement. Its six-token vocabulary
is the minimum that preserves the six equality classes in the frozen input.
Two layers are required to retain both the global and local attention forms.

## Measured comparison

| Measurement | Full model | Structural finalist | Ratio |
| --- | ---: | ---: | ---: |
| Serialized Torch-MLIR | 27,235,171 B | 109,426 B | 0.004018 (about 249x smaller) |
| End-to-end stage time | 5.889 s | 3.712 s | 1.586x faster |
| Torch-MLIR import time | 2.467 s | 0.820 s | 3.011x faster |
| Export/load time | 0.703 s | 0.262 s | 2.683x faster |
| MLIR render time | 0.043 s | 0.003 s | 15.7x faster |

Timings are one in-derivation measurement per configuration. The gap from the
10x gate is large enough that this is a clear negative result, not a
near-threshold benchmark claim.

## What the minimization established

- Position table 8 loses the boolean causal-mask `slice -> slice` and
  `slice -> where` dataflow. Position table 9 restores it.
- Width 1 loses `torch.aten.broadcast_to` and five related LayerNorm edges.
  Width 2 restores all required structure.
- A window of 1 also retains complete coverage at width 2, but emits 109,446
  B—20 B more than the 256-window finalist. Keeping the full-model window is
  both slightly smaller at this boundary and more conservative.
- The previously used W4A8 RC is deliberately outside this comparison because
  it contains hand-authored hardware substitutions.

## Interpretation and next boundary

The study has accomplished its narrow job: it produced a reproducible,
clean-configuration structural counterpart of the full PT2E W8A8 graph and
identified its smallest tested artifact. It did not produce an
orders-of-magnitude faster full-model lowering loop. The dominant remaining
cost is not serialized MLIR size alone: even the finalist's Torch-MLIR import
is only about 3x faster.

The appropriate next A/B is the full frozen PT2E W8A8 model versus this
structural finalist through an identical downstream lowering route, recording
where behavior and cost scale. Its full-model side must remain anchored to the
project's canonical numerical PT2E W8A8 reference, not merely this structural
calibration export, and functional equivalence remains a separate gate before
any hardware-validity claim. SmoothQuant, FPGA utilization, DDR3 integration,
and board execution remain out of scope for this result.
