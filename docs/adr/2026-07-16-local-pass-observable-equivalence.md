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

Verification has two explicit tiers. Every experiment first uses the frozen
four-case PT2E smoke oracle for rapid regression feedback. The complete
1,679,616-context comparison is required before a candidate is called
canonical, is adopted as the next baseline, or is described as RC observably
functionally equivalent. Until then it is labelled **provisional** regardless
of how many smoke cases pass.

The complete sweep is partitioned into deterministic, durable shards of the
base-six lexical token-context enumeration. Each shard records its inclusive
context-index range, expected count, reference and DUT provenance, result
digest, completion state, and any mismatch. A final manifest records every
shard digest and proves that the shard ranges are disjoint and cover exactly
`[0, 6^8)`. Shards and manifest are checked-in or Nix-produced durable
artifacts; transient working files are not evidence. This permits resumption
and parallel execution without relaxing the exhaustive requirement.

One raw-code mismatch, token-ID mismatch, invalid completion sequence, or
timeout rejects the candidate. The runner emits a durable counterexample packet
before any route is changed: token context and lexical index, PT2E and SV raw
codes and token IDs, reference/image/SV/tool hashes, declared timing contract,
and a cycle/handshake trace sufficient to replay the failure. A failed run may
stop at its first counterexample to conserve compute, but it cannot emit a
passing coverage manifest or be represented as partially accepted.

Each candidate declares a conservative, versioned worst-case cycle bound from
its documented launch event to its documented output-sampling event. Completion
outside that bound is a timeout and therefore a rejection. The smoke and
exhaustive artifacts record observed latency (including the maximum) against
that bound. PT2E supplies numerical behavior, not hardware-cycle timing, so
the gate requires correct bounded completion rather than cycle-for-cycle
agreement with PyTorch.

As soon as a first testable SV candidate exists, run a bounded deterministic
throughput probe before treating the full sweep as a routine promotion gate.
Its durable report records the candidate/SV/simulator/host provenance, sampled
context range and count, wall time, contexts per second, cycles per context,
peak resource use where available, and the projected cost of all `6^8`
contexts. The probe does not replace any smoke or exhaustive result; it
measures whether the verification contract itself is practical.

If the measured complete-sweep cost is impractical, record verification
scalability as a blocker with the probe, attempted execution strategy, and
limiting resource. The candidate remains provisional. Improve, shard, or
parallelize the verifier, or investigate a stronger proof method, but do not
substitute sampled testing for the exhaustive promotion gate or call the route
equivalent on smoke evidence alone.

Every newly observed lowering blocker follows an evidence ladder:

1. an existing upstream semantics-preserving dialect, pass, or library route;
2. an established published and openly inspectable implementation; then
3. a local implementation only when the earlier routes do not reach valid,
   testable SV.

The ladder decides investigation order, not acceptance evidence. Every route,
including an upstream one, still needs the same smoke, interface, timing, and
exhaustive-promotion gates before it can become canonical for the RC.

Blocker work proceeds one independent operation family at a time. An iteration
records the exact full-RC blocker, creates the corresponding minimal
reproducer and evidence-ladder result, integrates only the selected route and
its necessary documented dependencies, then reruns the complete RC lowering.
It must not bundle independent families such as `math.exp`, `math.tanh`, and
`math.fpowi`. The rerun produces either the next concrete frontier or a
testable-SV candidate for the normal promotion gates.

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
- Four matching smoke cases make an experiment suitable for rapid iteration,
  not for a canonical or functional-equivalence claim. The full finite sweep
  is the promotion gate.
- Interrupted or parallel exhaustive runs remain auditable only through the
  deterministic shard records and final complete-coverage manifest.
- A mismatch or timeout is a reusable negative result, not noise to suppress:
  it rejects the route and yields a replayable counterexample packet.
- Latency is a recorded implementation metric with a declared worst-case bound;
  it is not compared to PyTorch cycle-for-cycle.
- The first testable SV also produces a bounded verification-throughput probe,
  making the cost of the exhaustive gate a published result rather than an
  untested assumption.
- An impractical full sweep is a documented verification-scalability blocker;
  it does not weaken the definition of RC observable functional equivalence.
- The blocker evidence ladder makes upstream and published routes preferred
  investigative starting points, but no provenance class bypasses RC
  functional-equivalence evidence.
- One-blocker iterations preserve causality: a full-RC rerun after each
  intervention identifies the next frontier rather than hiding it in a bundle.
- The RC is valuable precisely because it makes this much stronger gate
  finite and potentially tractable; the same method is not automatically
  feasible for the full 50,257-token model.
