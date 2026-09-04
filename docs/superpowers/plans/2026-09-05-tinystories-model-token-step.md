# Plan: TinyStories-1M model-level token step

**Spec:** `docs/superpowers/specs/2026-09-05-tinystories-model-token-step-design.md`

## Tasks

## Task 1 — Freeze the exact model-level oracle

Freeze the exact model-level two-token oracle and boundary manifest from the
   authenticated TinyStories-1M package. Record embeddings, every configured
   block, final LayerNorm, tied LM head, greedy token selection, and the
   initial/feedback token contract. Add tests that reject host-provided second
   token or intermediate-state substitution.
## Task 2 — Implement the compiler-owned orchestrator

Implement a compiler-owned orchestrator that composes the existing stateful
   block backend with generated embedding, final LayerNorm, LM-head, and token
   feedback memories. Keep the existing block datapath unchanged.
## Task 3 — Generate and execute the linked token steps

Generate one Calyx/SV main and bounded harness for two hardware-linked token
   steps, with reset/restart isolation, exact boundary hashes, and no host
   intermediate preload.
## Task 4 — Close the evidence gates

Run same-Futil simulation/synthesis and Yosys statistics; emit a
   self-hashed receipt and deterministic failure diagnostics. Perform a whole
   goal audit before claiming completion.

## Global constraints

- Exact authenticated TinyStories-1M model and fixed-point contract only.
- No DDR3, PCIe, board, Representative Core, or arbitrary-model scope.
- Every compiler/build subprocess is bounded.
- Use the existing generated block implementation as a composition boundary;
  do not copy or import kev-gpt RTL.
