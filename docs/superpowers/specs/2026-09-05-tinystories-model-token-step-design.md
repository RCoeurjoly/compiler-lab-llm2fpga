# TinyStories-1M Model-Level Token-Step Design

## Objective

Extend the authenticated TinyStories-1M fixed-point compiler path from a
stateful block-0 wrapper to a compiler-owned model-level token-step. The
generated design must perform the exact model's token/position embedding,
configured transformer blocks, final LayerNorm, tied LM head, and deterministic
greedy token selection.

The acceptance workload is two consecutive token steps in one generated
Calyx/SystemVerilog main. The token selected by the first step is produced by
the hardware and is consumed by the second step's embedding lookup. The host
may preload immutable model tensors and the initial token only; it may not
provide intermediate hidden states, logits, or the second token.

## Contract

The top level exposes `clk`, `reset`, `start`, `valid`, and `done`, with
compiler-owned state, token-feedback, logits, and boundary memories. Reset
returns the orchestrator to its initial-token state. Every model boundary has
an independently hashed fixed-point checkpoint against the authenticated
PyTorch oracle. Simulation and synthesis consume the same Futil and emit a
self-hashed provenance receipt plus Yosys resource statistics.

## Fast-learning gates

- Development fixtures and structural checks complete within 30 minutes.
- A full exact-model generated build is bounded by two hours; no unbounded
  compiler invocation is permitted.
- A failure must identify the first divergent model boundary or compilation
  stage rather than silently falling back to a host-computed result.

## Scope exclusions

This milestone does not include FPGA board programming, DDR3, PCIe,
Representative Core substitution, arbitrary-PyTorch generality, or copied
kev-gpt RTL. It is a generated RTL/simulation milestone; board execution is a
subsequent goal after this path is proven.
