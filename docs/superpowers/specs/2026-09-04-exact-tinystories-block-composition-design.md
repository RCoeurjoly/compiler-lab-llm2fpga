# Exact TinyStories-1M Complete Block Composition Design

## Purpose

The next compiler milestone is a complete, compiler-owned TinyStories-1M
block-0 execution for the authenticated four-token prompt. It composes the
already verified attention-to-c_fc boundary and c_fc-to-c_proj MLP crossing
without a host tensor handoff. This is the reusable block template on the
route to a full forward pass and, later, autoregressive decoding; it is not
itself a full-model or token-generation claim.

## Scope

One generated Calyx `component main` executes all four block-0 rows:

`block input -> ln_1 -> Q/K/V QDQ and GEMVs -> causal attention -> out
projection QDQ and GEMV -> attention residual -> ln_2 -> c_fc QDQ and GEMV
-> fixed GELU -> c_proj QDQ and GEMV -> final block residual`.

The required final output is `block_output_q16_16[4,64]`. A design ending at
c_proj is incomplete because it has not demonstrated the final residual
addition.

This milestone excludes embeddings, blocks 1–7, final LayerNorm, LM head,
token selection, KV-cache persistence, an autoregressive control loop, board
execution, DDR3, PCIe, Representative Core, generic-SCF/arbitrary-PyTorch
generality, and copied or wrapped reference RTL.

## Semantic and fixture authority

`_ExactFixedPointModel` remains the sole semantic authority, authenticated by
the frozen exact-input contract, package, and prompt `[7454, 2402, 257, 640]`.
The design preserves its Q16.16/Q8.24 arithmetic, signed-int8 Q/DQ,
ascending signed-64-bit wrapping MAC, fixed LayerNorm, causal exp-LUT and
division behavior, fixed GELU LUT, signed-magnitude half-up rescale, and
residual additions.

The new block-composition fixture is self-hashed and links, by authenticated
receipt and per-record hash, both existing fixtures:

- `tinystories-1m-fixed-point-attention-crossing-slice.json` supplies the
  block input through c_fc input Q/DQ authority.
- `tinystories-1m-fixed-point-mlp-crossing-slice.json` supplies c_fc through
  c_proj authority.
- the new fixture supplies only `block_output_q16_16[4,64]`, captured from
  the exact adapter and replayed as `attention_residual + c_proj_output`.

It must reject a linked-fixture identity mismatch, a linked record mismatch,
or a residual replay mismatch. It does not duplicate the 61 attention or 25
MLP records; their existing self-hashed fixtures remain authoritative.

## Direct composition

All computed values are generated-hardware memories. `ln_2` is read directly
by c_fc input Q/DQ, and attention residual remains in generated memory until
the final add with generated c_proj output. The harness can preload only
immutable source input, parameters, codes, scales, and lookup tables. It may
zero checkpoint memories but cannot preload expected values, c_fc inputs,
GELU values, c_proj values, residuals, or block output.

The compiler-owned lowerer may reuse its prior generated arithmetic primitives
and schemas, but must emit the composed control/memory graph itself. It may
not instantiate, copy, or wrap RTL from the reference accelerator. `cell-share`
may be disabled only if the same documented generated-Calyx combinational-loop
failure still applies; simulation and synthesis must consume the same Futil.

## Acceptance and receipt

One generated-SV run must read and compare every hardware-produced checkpoint
from both linked fixtures and the final block output. The receipt must bind:

- all three fixture receipts and their linked identities;
- one component count, directness/source-only memory partition, and cycle
  count;
- observed hashes for every attention checkpoint, every MLP checkpoint, and
  `block_output_q16_16`;
- Futil, simulation-SV, synthesis-SV, and harness hashes; and
- a canonical self-hash.

The acceptance CLI must authenticate all fixtures, validate the receipt,
assert one `main` and no expected-output preload, and run Yosys on SV derived
from the identical Futil. Report generic synthesis counts and simulator cycles
only; do not represent them as board fit, timing, throughput, latency, or
inference evidence.

## Failure policy and quit point

The first divergent named checkpoint is the only permitted localization target.
No speculative RTL change may skip it. Each composition attempt must produce a
useful generated artifact or diagnostic within 30 minutes. After two
evidence-backed composition failures, stop and record whether the missing
abstraction is a compiler-schema issue; do not broaden scope into top-level
forward execution or substitute copied RTL.

## Successor boundary

On success, this milestone establishes a complete exact block template. The
next separate goal may generalize that template across the fixed eight layers
and add embeddings, final LayerNorm, and LM head for a single exact forward
pass. Stateful KV-cache and greedy autoregressive decoding remain a subsequent
goal.
