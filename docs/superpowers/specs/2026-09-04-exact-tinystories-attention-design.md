# Exact TinyStories-1M Attention Crossing Design

## Purpose

Extend the authenticated, compiler-owned fixed-point TinyStories-1M backend
from the proven block-0 MLP crossing to the preceding block-0 attention path.
The deliverable is generated Calyx/SV evidence, not a board implementation or
a general PyTorch lowering claim.

## Scope and authority

The sole semantic authority is `_ExactFixedPointModel` in
`TinyStories/model_adapter_exact_package.py`, authenticated through the frozen
exact-input contract, package, and four-token prompt `[7454, 2402, 257, 640]`.
The implementation must capture a new four-row fixture from its block-0 trace
and bind it to the existing MLP fixture's `c_fc_input_{codes,scale,q16_16}`
records. The shared values must be equal bit-for-bit; neither fixture may be
treated as an independently chosen input.

This work covers exactly one block-0, four-prompt-row slice:

`ln_1 -> Q/K/V GEMVs and Q/DQ -> causal attention -> out-projection GEMV and
Q/DQ -> residual addition -> ln_2 -> c_fc input Q/DQ`.

It excludes complete transformer execution, autoregressive token generation,
board execution, DDR3, PCIe, Representative Core substitution, generic-SCF or
arbitrary-PyTorch lowering, and copied reference RTL. Existing reference RTL
may be used only as historical semantic evidence, never instantiated, copied,
or wrapped by the generated design.

## Exact fixed-point contract

The adapter's integer behavior is the contract, including:

- signed Q16.16 values and unsigned per-channel Q8.24 activation/weight
  scales;
- activation Q/DQ using signed-int8 saturation and nearest,
  ties-away-from-zero conversion;
- ascending-input-index, signed-64-bit two's-complement-wrapping GEMV MAC;
- signed-magnitude half-up weight rescale by 32 bits and Q16.16 bias after
  rescale;
- fixed LayerNorm: truncating signed mean, `variance + 42950`, restoring
  integer square root, truncating signed division, and Q16.16 affine;
- 16 heads of width 4; causal positions 0..3; score `sum(q*k) >> 24`;
  maximum subtraction; delta clamp `[-4096,0]`; a 4096-entry Q1.20 exp LUT;
  exact zero-delta `1<<20`; and the adapter's signed rounded/truncating
  attention-value division;
- out-projection, residual, second LayerNorm, and the c_fc input Q/DQ
  boundary.

No host floating-point calculation, synthesized approximation, reordered
reduction, or uncaptured rounding rule can replace an operation above.

## Fixture and provenance

`capture_fixed_point_attention_crossing_slice.py` will authenticate the
adapter before capturing four rows and self-hash the resulting fixture. It
will record all source tensor values, semantic roles, shapes, canonical hashes,
raw little-endian signed-i64 hashes, byte counts, and a fixture-binding receipt.

The fixture must include, at minimum:

- block input; `ln_1` output; `ln_1` gamma/beta;
- each Q/K/V input QDQ, accumulator, post-rescale result, output QDQ, weight
  codes/scales, and biases if present;
- causal attention score, maximum, clamped delta, exp probability,
  denominator, numerator, and context for all four rows and 16 heads;
- out-projection input QDQ, accumulator, post-rescale+bias, output QDQ,
  weights/scales/bias;
- attention residual; `ln_2` gamma/beta and output; and the c_fc input QDQ.

The existing MLP fixture's `c_fc_input_codes_i8`,
`c_fc_input_scale_q8_24`, and `c_fc_input_q16_16` must be recorded as linked
authority and verified equal at capture and generated-SV-run time.

## Generated hardware and directness

The final lowering emits exactly one Calyx `component main`. It owns all
intermediate memories and sequencers; a value produced by one phase is read by
the next phase directly from generated hardware memory. The harness may
preload only immutable source inputs, parameters, weight codes/scales,
activation scales, and the exp LUT. It must not preload any computed
checkpoint, expected-result array, Q/K/V result, attention context,
out-projection result, residual, `ln_2`, or c_fc input boundary.

The compiled artifact may disable `cell-share` only where required to preserve
explicitly staged fixed-point latches. Both simulation and synthesis must
consume the same emitted Futil source.

## Staged verification and final acceptance

Development uses two diagnostic generated-SV gates: fixed `ln_1` and the
causal-attention context. They localize failures but do not satisfy this
specification individually.

Final acceptance requires one generated-SV execution whose post-run reads of
every captured intermediate and final checkpoint are bit-identical to the
fixture. In particular, it must prove exact `ln_2[4,64]` and the three c_fc
input Q/DQ records, including equality with the prior MLP fixture. The runner
must produce a canonical self-hashed receipt binding fixture and linked-MLP
authority, compiler-owned schema authority, component count, cycle count,
all observed hashes, and Futil/simulation-SV/synthesis-SV/harness hashes.

The acceptance CLI runs the full observed-checkpoint comparison and same-Futil
Yosys stat. The receipt must state only generic synthesis counts and simulator
cycles; neither is a board-fit, timing, latency, throughput, or inference
claim.

## Failure handling and stopping rule

The first named mismatching checkpoint is the sole permitted localization
target; no speculative change may skip over it. A full composition attempt is
bounded and must emit a useful artifact or diagnostic within 30 minutes. After
two evidence-backed full-composition failures, stop implementation and record
whether the failing semantic needs a schema redesign rather than expanding
scope or substituting reference RTL.
