# RC Softmax-Exponent Domain and Open-IP Survey Design

## Purpose

Reduce the `math.exp` blocker uncertainty without changing the frozen
`tinystories-w8a8-rc-study-mask9-vocab6-width2` PT2E W8A8 model, its
calibration, its graph, or its compiler route. The work has two outputs:

1. an exhaustive, deterministic characterization of the two frozen RC
   attention-Softmax exponent operand domains; and
2. an auditable survey of reusable open exponent/Softmax implementation
   candidates.

Neither output integrates a candidate, emits new RC SV, or claims functional
equivalence.

## Observed source boundary

The frozen exported PT2E graph has two `torch.ops.aten.softmax.int` nodes.
It does not directly contain `aten.exp`; Torch-MLIR decomposes each Softmax
into maximum subtraction, `exp`, summation, and division. Therefore the
analyzer will execute the frozen PT2E graph unchanged, observe each Softmax
input, and compute the *analysis-only* stabilized operand with f32
`input - amax(input, dim=-1, keepdim=True)`. It will call this value
`derived_pre_exp_operand`, not claim that a separately executed Python
calculation is a new canonical model or an operation-level proof of the
lowered `math.exp` input.

Both observed Softmax inputs are the immediate f32 dequantizations of signed
int8 tensors with scale `0.000244140625` (`2^-12`), zero point `-124`, and
the range `[-128, 127]`. The corresponding Torch-MLIR provenance slices have
shape `[1, 1, 8, 8]` and reduce along the final dimension. Consequently each
site has at most 256 distinct observed input codes and at most 256 distinct
max-subtracted values under this exact affine quantize/dequantize boundary.
The exhaustive run still observes and proves the actual sets rather than
assuming all codes occur. It processes 64 values per Softmax site per context
(214,990,848 site-values across the full context space), so streaming rather
than trace retention is a design requirement.

## Domain-characterization design

A read-only `torch.fx.Interpreter` over `torch.export.load(...).module()`
will intercept only the two `aten.softmax.int` calls. It forwards every call
to the original target and records a streaming summary of the operand
derivation. It does not patch, re-export, calibrate, or persist a modified
graph.

The input space is enumerated in base-six lexical order over all
`[0, 6^8) = [0, 1,679,616)` token-context indices. The runner supports
deterministic half-open shards `[start, stop)` so a pilot, resumption, and
complete merge are auditable. Each shard records:

- source model key, exported-program SHA-256, exported manifest SHA-256,
  analyzer SHA-256, enumeration convention, and index range;
- the two Softmax node names, input shapes/dtypes, and upstream
  quantize/dequantize parameters found from the frozen FX graph;
- sample count, finite/NaN/infinity counts, positive-pre-exp count, numeric
  minima/maxima, and exact observed f32 bit-pattern sets for the Softmax
  input and derived exponent operand; and
- wall-clock duration and contexts/second.

The implementation must validate the derived, per-site 256-value cardinality
bound and fail explicitly rather than silently approximate or discard values.

A reducer merges only compatible shard reports, proves non-overlap and
complete coverage for the exhaustive result, recomputes exact unique counts,
and emits a durable final manifest. The four frozen corpus cases form the
fast smoke run; they never substitute for complete coverage.

## Open-IP survey design

The survey is an evidence document, not a dependency update or an import of
third-party RTL. Each candidate receives one of these classifications:

- **direct integration candidate** — open source, explicitly licensed,
  synthesizable hardware source, and a plausible f32 exp or full-Softmax
  interface for a Calyx external primitive;
- **translation candidate** — potentially useful generated/source hardware
  but requiring a new language/backend boundary, such as VHDL-to-current-SV
  integration; or
- **algorithm/reference only** — useful method or precedent but not
  independently reusable RTL/IP for the current pipeline.

For every investigated candidate, record its canonical project URL, pinned
revision when obtainable, license evidence, implementation language/output,
supported precision and numerical contract, control/latency interface,
verification evidence, current-flow import feasibility, and reason for the
classification. The survey retains short paraphrases and metadata only; it
does not vendor or copy external source code.

## Decision and trust boundaries

The characterization can make a future range-bounded candidate defensible,
but cannot admit it. A borrowed or local exp/Softmax component remains
provisional until it reaches a valid testable RC SV interface and passes the
existing frozen PT2E smoke and exhaustive `6^8` observable-functional-
equivalence gates. The only numerical authority remains the frozen PT2E
W8A8 evaluator.

A future candidate must declare source, license, numerical contract, range
assumptions, reset/launch/completion behavior, and a conservative cycle
bound. This design explicitly defers candidate selection, Calyx integration,
approximation choice, DDR3 work, resource claims, and board work.

## Acceptance evidence

- Unit tests demonstrate base-six context decoding, FX Softmax-node
  discovery, stable operand derivation, bit-pattern accounting, shard
  compatibility, and complete-coverage rejection of gaps/overlaps.
- A Nix-produced pilot confirms deterministic four-case results and records
  throughput before the full sweep.
- A Nix-produced exhaustive manifest covers exactly `6^8` contexts, or a
  durable scalability blocker reports the measured pilot, attempted full
  execution, and limiting resource without weakening the requirement.
- A checked-in result document records the actual domain outcome and limits.
- A checked-in survey records every candidate and makes no assertion that
  any source proves PT2E-to-SV equivalence.
