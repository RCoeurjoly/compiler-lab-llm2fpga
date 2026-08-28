# ADR 0009: select the TinyStories-1M fixed-point profile only from a board-bound trace

## Status

Accepted — unresolved pending a recorded YPCB TinyStories-1M trace.

## Context

The original frozen contract records the inspected package's historical summary:
signed INT32 accumulation and per-tensor activation INT8.  The independently
authenticated AGPL reference package, fixed executable oracle, and
synthesizable GEMV instead establish a candidate fixed-point implementation
with a serial signed-INT64 accumulator, one Q8.24 scale for each activation
channel, ties-away-from-zero activation/requantization, and signed INT8 clamp
`[-128, 127]`.  Those are genuine semantic conflicts, not formatting details.

`artifacts/kintex-selftest/provenance.json` is preserved as evidence for a
YPCB self-test image only.  It contains neither a TinyStories bitstream nor a
frozen-prompt result nor the twelve block-0 checkpoint tensors.  It cannot
select the candidate profile.  The candidate runtime oracle is likewise not a
board trace.

## Decision

`scripts/comparison/select_tinystories_1m_implementation_profile.py` writes
the versioned profile receipt.  With the evidence currently in the repository,
the checked-in receipt is `unresolved` and no comparison adapter or compiler
path may claim the fixed profile.

A future receipt may select `fixed_hardware_reference` only when it binds:

- the frozen Task-1 contract and authenticated Q/DQ receipt hashes;
- YPCB-00338-1P1, the programmed bitstream hash, and every authenticated
  reference-source hash;
- the frozen prompt and all sixteen expected output tokens; and
- all twelve exact block-0 token-step checkpoint tensors, including their
  trace hash, equal to the fixed-point runtime oracle.

The selection records a supersession only for numeric implementation semantics;
the original Task-1 contract remains immutable source/package identity.  A
malformed, conflicting, or incomplete receipt leaves the profile unresolved.
No RTL, transport, or optimization change is made by this decision.

## Consequences

The compiler comparison remains blocked at the profile gate rather than
silently comparing a compiler INT32/per-tensor implementation to an INT64/
per-channel hardware implementation.  The exact new artifact required to
unblock it is a content-bound `tinystories-1m-board-checkpoint-receipt-v1`.

The reference remains AGPL-3.0-only and is used only as an authenticated
behavioral oracle; neither its source nor RTL is copied into compiler output.
