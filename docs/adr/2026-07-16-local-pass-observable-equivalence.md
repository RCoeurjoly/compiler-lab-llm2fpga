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
This decision does not approve a changed numerical contract or an
approximation; those require their separate decision under the existing
canonical-PT2E policy.

## Consequences

- A primitive MRC, an emitted HardFloat module, a successful compiler pass,
  and four matching reference cases are useful evidence but cannot promote a
  local transform into the canonical RC route.
- The first `math.exp` blocker investigation may continue without an SV
  result. Any future integration plan for a local transform must include the
  exhaustive checker before making a canonical claim.
- The RC is valuable precisely because it makes this much stronger gate
  finite and potentially tractable; the same method is not automatically
  feasible for the full 50,257-token model.
