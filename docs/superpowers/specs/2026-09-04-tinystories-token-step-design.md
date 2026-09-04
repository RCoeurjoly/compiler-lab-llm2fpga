# TinyStories-1M Stateful Token-Step Design

## Goal

Wrap the authenticated four-row block-0 generated Calyx/SV datapath in a
compiler-owned stateful transaction interface.

## Contract

The generated top-level `main` must expose `clk`, `reset`, `start`, `valid`,
and `done`, plus input-state and output-state memories. `reset` clears the
transaction state; `start` is accepted only when idle; `valid` qualifies an
input-state transaction; and `done` is asserted only after the block has
consumed the accepted state and committed the output state.

One simulation must issue two back-to-back transactions after reset. The
second transaction must read the first transaction's hardware-produced output
state through the generated memory handoff, not through host-provided expected
data. Both outputs, transaction ordering, reset behavior, and cycle counts must
match an independently replayed fixed-point oracle bit-for-bit. Simulation and
synthesis must consume the same Futil and record a self-hashed receipt.

## Scope exclusions

This slice does not claim embeddings, remaining transformer blocks, final
LayerNorm, LM-head/token selection, full autoregressive generation, board
execution, DDR3, PCIe, Representative Core substitution, or copied RTL.
