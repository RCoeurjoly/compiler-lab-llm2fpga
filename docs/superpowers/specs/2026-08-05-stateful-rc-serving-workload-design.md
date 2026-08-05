# Stateful serving-workload representative-core design

## Status and decision

**Status:** approved design; implementation has not started.

Keep the existing V=6, context-8, stateless PT2E W8A8 representative core as
a fast compiler and equivalence fixture. Add a distinct **stateful serving
RC** whose purpose is to exercise the control and state semantics of a small
autoregressive workload: prompt prefill, cached decode, cache growth, reset,
and host token feedback.

The serving RC is deliberately not a quality, resource-scaling, or
full-TinyStories proxy. It may retain random deterministic weights, V=6, two
layers, width two, and one head. Its claim is narrower: a direct lowering of
the source model's fixed cached-serving trace preserves the model's observable
logits, tokens, and native cache values.

The source model remains authoritative. No hand-written attention, causal
mask, cache-update, position, or numerical-model implementation is permitted
in the canonical route. Compiler tools lower the graph they receive; changing
those semantics in an adapter would move functional-drift risk upstream of
Torch-MLIR, MLIR, CIRCT, Calyx, and RTL verification.

## Goals

1. Preserve the unmodified Hugging Face TinyStories RC model semantics with
   use_cache=True.
2. Exercise one fixed serving trace: eight-token prefill followed by two
   cached decode calls.
3. Make cache state an explicit, auditable input/output boundary between model
   invocations without changing cache values or layout.
4. Establish exact PyTorch-to-export-to-SV evidence for logits, greedy token
   feedback, and every native cache tensor leaf.
5. Introduce a persistent RTL cache store only after the direct cache-boundary
   trace passes.

## Non-goals

- Predict full TinyStories or larger-model quality, fit, throughput, or power.
- Change the existing stateless RC's reference, acceptance criteria, or
  compiler-regression role.
- Introduce dynamic prompt lengths, unbounded decoding, batching, sampling,
  beam search, or a full human tokenizer.
- Reuse historical one-token attention simplifications or causal-mask removal.
- Quantize, transpose, pack, pad, slice, or otherwise transform cache values
  in the model-facing adapter.
- Claim that a host/testbench-held cache is already a persistent FPGA-memory
  implementation.

## Fixed workload contract

The serving RC has a fixed maximum position capacity of ten. The current
structural RC profile has nine position embeddings; it must not be reused
unchanged because an eight-token prefill plus two decode inputs consumes
positions zero through nine.

The deterministic transaction is:

~~~text
prefill-8
  input:  prompt token IDs [1, 8], source-model empty cache
  output: last-position logits predicting token_8, native cache C8

decode-8
  input:  greedy token_8 [1, 1], C8
  output: logits predicting token_9, native cache C9

decode-9
  input:  greedy token_9 [1, 1], C9
  output: logits predicting token_10, native cache C10
~~~

Greedy selection uses the existing lowest-index tie rule. Sampling is
intentionally host-side and out of scope: deterministic feedback is sufficient
to exercise the autoregressive loop. The cache must contain valid positions
0..7 after prefill, 0..8 after decode-8, and 0..9 after decode-9.

The source model's own handling of attention mask, cache_position, position
IDs, and native past_key_values is retained. The implementation must not
substitute an inferred mask or independently calculate cache positions.

## Source-model and export boundary

### Direct native-cache path

The first and preferred path calls the ordinary source model with
use_cache=True, passes the native returned cache into the next ordinary model
call, and exports that direct interface. The exact native cache representation
depends on the pinned Transformers version and model implementation; it is
observed and recorded, not assumed in advance.

The three static export targets are intentionally separate because their input
shapes differ:

~~~text
prefill-8: input IDs [1, 8], source-model empty-cache form
decode-8:  input IDs [1, 1], native cache C8 shape/schema
decode-9:  input IDs [1, 1], native cache C9 shape/schema
~~~

This is a fixed workload fixture, not a generic dynamically shaped server.
Separate exports avoid hiding a dynamic-cache mechanism in the compiler while
still proving cache growth across the two meaningful transitions.

### Conditional mechanical cache-ABI shim

Only if direct torch.export or the next frontend cannot accept the native
container may an ABI shim be proposed. It may only flatten and reconstruct the
native tensor tree using a recorded ordered schema. It must contain no tensor
arithmetic, casts, device moves, reshape, transpose, concat, slice, padding,
masking, cache append, position calculation, or model-parameter access.

The shim's sole permitted mapping is:

~~~text
native cache tensor tree <-> ordered identical tensor leaves
~~~

The schema records each leaf's ordinal, tree path, dtype, shape, byte count,
and byte digest. A direct-source run and a shimmed-source run must have
bit-identical logits and every cache leaf for all three transactions. A
frontend failure is evidence to preserve; it is not permission to replace
native cache semantics with a hand-written model.

## Cache storage boundary

The ordered native cache leaves are the logical cache ABI. Their later storage
image is a lossless serialization of those leaves, not a new model-facing
tensor representation. The serialization schema must specify leaf order,
element dtype, endianness, byte offset, byte length, valid-position range, and
an overall digest.

The first SV-chain test uses a host or testbench service that retains the
returned cache bytes verbatim and supplies them to the next generated module.
This proves the compiler and generated design across a cached-serving trace.

Only after that gate passes may a separate RTL cache-store component replace
the host/testbench service. The store is a byte-preserving state service, not
a transformer implementation. It must reset/invalidate a session, retain
C8/C9/C10 across invocations, and reject out-of-range or schema-mismatched
requests. Its tests are separate from model-equivalence tests.

## Acceptance and promotion gates

### Gate 0 — native PyTorch serving reference

Run the ordinary source model with use_cache=True through the fixed trace.
Verify that chained prefill/decode calls and deterministic greedy generation
select the same two generated tokens. Record prompt IDs, all three logits,
tokens 8 through 10, native cache schema, and C8/C9/C10 leaf hashes.

### Gate 1 — direct export conformance

For each static target, run eager source PyTorch and its torch.export module
on the same native cache input. Require exact raw output-code equality and
bit-identical cache leaves. Any discrepancy rejects the export; no tolerance
is silently substituted.

### Gate 2 — conditional shim conformance

This gate exists only if Gate 1's direct container interface is blocked by a
recorded tool limitation. Inspect the shim's exported graph to ensure it has
only container/leaf plumbing, then require the same exact evidence as Gate 1.
The shim cannot become canonical merely because it enables compilation.

### Gate 3 — frontend acceptance

Lower the accepted direct interface, or the Gate-2-qualified shim, through the
existing toolchain. Preserve exact artifacts, tool versions, native schema,
and the cache ABI receipt. A lowering failure is a compiler frontier result,
not an invitation to alter source-model semantics.

### Gate 4 — generated-SV chained serving trace

Run generated SV in the prefill-8 -> decode-8 -> decode-9 order. The
testbench/host retains cache leaves verbatim between calls. Require exact
logits and token IDs at every call, C8/C9/C10 cache-leaf equality, correct
valid-position growth, and no mutation of an already valid cache prefix.

### Gate 5 — persistent cache-store integration

Replace only the host/testbench retention service with the RTL cache store.
Repeat Gate 4 unchanged. Add reset isolation, stale-state rejection,
read-after-write, bounds, and byte-image round-trip tests. Passing this gate
is the first serving-RC state-storage claim; it is not DDR3 or board proof.

## Failure handling and evidence

Every failure records source/export/SV/cache-schema identities, transaction
phase, cache input and output hashes, logical valid length, expected and
observed logits/tokens, and the earliest failing cache leaf or byte range.

The runner must reject, rather than repair:

- a cache tree with changed leaf count, order, dtype, or shape;
- an unknown native-cache representation;
- a cache image whose schema or digest does not match the generated target;
- writes outside the declared next-position range;
- a mutation of a previously valid cache prefix;
- a decode request issued with an invalid cache length; and
- use of stale cache contents after reset/new request.

Zero-filled padding may exist only when declared in the cache-image schema and
excluded from model-visible native leaves. It must never silently coerce
incompatible cache shapes.

## Implementation sequencing

1. Create the native PyTorch use_cache=True reference and its immutable
   serving-trace receipt.
2. Probe direct torch.export for prefill-8, decode-8, and decode-9 before
   writing any shim.
3. Add the conditional mechanical shim only if the probe identifies a concrete
   container limitation and Gate 2 is satisfiable.
4. Add native-cache schema and lossless image-serialization tests.
5. Extend the generated-SV harness to retain and refeed cache state across the
   three calls.
6. Implement the independent persistent RTL cache store and repeat the
   unchanged serving trace.

The work stops and publishes a blocker at any failed gate. It does not solve
frontend or RTL difficulties by changing the model's cache semantics.

