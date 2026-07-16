# ADR: Admit local RC transforms through exhaustive observable equivalence

- Status: accepted
- Date: 2026-07-16

## Context

The project prefers established PyTorch, Torch-MLIR, MLIR, TOSA, CIRCT, Calyx,
and HardFloat paths because their semantics, implementations, and maintenance
are independently inspectable. That preference does not make a local compiler
plugin or pass intrinsically invalid.

A four-case frozen PT2E W8A8 reference image is a useful regression smoke
oracle, but it cannot establish the behavior of the complete representative
core over all of its possible token inputs. A local transformation that happens
to match those four cases would not have enough evidence to become a canonical
pipeline component.

The project needs one numerical authority, not several mutually unverified
implementations. The frozen PT2E W8A8 evaluator is that authority. A
hand-written integer model, hardware-oriented reference model, or independent
approximation may help diagnose a failure, but cannot become an acceptance
oracle for the canonical RC route.

The frozen RC has a finite, small externally visible input domain: vocabulary
size six and context length eight. There are exactly `6^8 = 1,679,616` token
contexts when every position ranges over token IDs `0..5`.

## Decision

A local compiler transform may enter the canonical frozen-RC pipeline only
after it reaches valid, testable SV and demonstrates exhaustive observable
functional equivalence at the RC token interface:

1. For every one of the 1,679,616 length-eight token contexts, reset the DUT
   to the same deterministic state and use the same frozen model image.
2. Run the frozen PT2E W8A8 reference and the generated SV for that context.
   Any stored or sharded expected-output corpus must be generated directly
   from that evaluator and record its evaluator, converted-graph, model-image,
   enumeration, and shard hashes.
3. Require equality of all six final raw int8 output codes and the
   lowest-index argmax token ID.
4. Record tool versions, pass provenance, generated-SV hash, reference-image
   hash, the enumeration order, completion count, and any mismatch in a
   reproducible artifact.

The existing four-case reference image remains the fast smoke/regression
oracle. It is not called a functional-equivalence proof.

For this fixed deterministic RC and this fixed token-input interface, a
successful exhaustive comparison is called **RC observable functional
equivalence**. It does not establish equivalence for full TinyStories, for a
larger vocabulary or context, for unexposed internal signals, for timing, or
for a changed model image.

Established upstream lowering remains preferred because it reduces the
semantic and maintenance burden. A local transform that passes this gate is
not hidden: its source, provenance, result, and limitations remain published.

For this fixed RC, a local implementation may use an approximation or a
custom special-function algorithm if, and only if, it passes the exhaustive
gate above. That admission establishes *RC observable functional equivalence*,
not operation-level equivalence to `math.exp` or a general PT2E semantics
claim. The implementation must be labelled accordingly and publish its exact
source, numerical contract, range assumptions, and exhaustive-test result. It
cannot be described as a canonical Full TinyStories transform or promoted to a
larger model without a new equivalence argument and test.

The exhaustive gate is reusable, not exceptional. It must be rerun after each
semantics-affecting frozen-RC transformation, including base lowering, a local
math implementation, and memory externalization. For external memory, the
gate uses an image-backed SV memory fixture that serves the same immutable
frozen model image to both candidates. A DDR3-controller or board run is a
separate physical-integration gate: it establishes service protocol, timing,
and hardware behavior, but does not replace the exhaustive image-backed
numerical comparison.

A candidate is a **testable RC SV implementation** only when its documented
top-level interface makes the eight token inputs controllable and makes all six
raw output codes plus the token ID observable. It must also define clock,
reset, launch, completion, and the cycle or handshake condition at which those
outputs are sampled. Internal hierarchical probes and an otherwise opaque
`done`-only interface do not satisfy this contract. Such output may still be
kept as a resource-only scout, but it cannot claim RC observable functional
equivalence or become a canonical RC implementation.

## Consequences

- A primitive MRC, an emitted HardFloat module, a successful compiler pass,
  and four matching reference cases are useful evidence but cannot promote a
  local transform into the canonical RC route.
- A separately implemented integer or hardware-style model cannot replace
  PT2E as the acceptance oracle. It may be retained only as diagnostic evidence
  whose disagreement triggers investigation, not a vote over correctness.
- The first `math.exp` blocker investigation may continue without an SV
  result. Any future integration plan for a local transform must include the
  exhaustive checker before making a canonical claim.
- A local `math.exp` replacement that meets the exhaustive fixed-RC gate can
  become canonical for the RC even if it does not preserve an operation-level
  `math.exp` contract. Its claim must remain bounded to the fixed RC.
- An external-memory change needs two kinds of evidence: exhaustive equality
  with the deterministic image-backed fixture and separate DDR3/board evidence.
  Passing either one alone is not the complete claim.
- A Calyx, CIRCT, or other generated SV module with only a `done`-style visible
  interface is a resource scout rather than a functional RC candidate until a
  documented testable wrapper exposes the RC inputs and outputs.
- The RC is valuable precisely because it makes this much stronger gate
  finite and potentially tractable; the same method is not automatically
  feasible for the full 50,257-token model.
