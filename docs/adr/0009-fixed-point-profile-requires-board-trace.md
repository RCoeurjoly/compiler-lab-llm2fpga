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

The inspected external receipt at
`/home/roland/kev-gpt/.worktrees/kintex-selftest/artifacts/kintex-selftest/provenance.json`
is evidence for a YPCB self-test image only.  It contains neither a
TinyStories bitstream nor a frozen-prompt result nor the twelve block-0
checkpoint tensors.  It cannot select the candidate profile.  The candidate
runtime oracle is likewise not a board trace.

## Decision

`scripts/comparison/select_tinystories_1m_implementation_profile.py` writes
the versioned profile receipt.  With the evidence currently in the repository,
the checked-in receipt is `unresolved` and no comparison adapter or compiler
path may claim the fixed profile.

A future receipt may select `fixed_hardware_reference` only against the pinned
canonical Task-1 and Q/DQ artifact hashes, and when its exact
receipt-file SHA-256, bitstream-file SHA-256, and capture-file SHA-256 have
first been added to the source-controlled approval registry following evidence
review.  A self-hashed JSON file is not approval.  The receipt must bind:

- the frozen Task-1 contract and authenticated Q/DQ receipt hashes;
- YPCB-00338-1P1, an existing programmed-bitstream file whose bytes match the
  declared hash, and every authenticated reference-source hash;
- the frozen prompt and all sixteen expected output tokens; and
- an existing, separately hashed `board_debug_csr_readback` capture file with
  all twelve exact block-0 token-step checkpoint tensors, including their
  recomputed checkpoint and trace hashes, equal to the fixed-point runtime
  oracle; and
- existing, separately hashed raw board transcript, capture-tool, and capture-
  protocol files, plus a separately hashed bitstream build manifest bound to
  the programmed bitstream bytes.

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
