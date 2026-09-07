# TinyStories-1M BRAM-only production design

## Objective

Derive a production compiler output from the validated two-token
TinyStories-1M model orchestrator. Preserve its fixed-point behavior and
hardware token feedback while removing memories that exist only to retain
audit checkpoints. Stream the tied LM-head reduction directly into the greedy
argmax so no full-vocabulary logits buffer is required.

## Required behavior

The production main keeps `start`, `valid`, `done`, and `reset`, accepts only
the authenticated immutable source tensors and frozen four-token prompt, and
executes two generated token steps. The selected token is written by hardware
to the next context slot. A production simulation must still reproduce the
oracle tokens and final outputs without host intermediate-state or second-token
input.

## Resource and implementation gates

- No audit-only embedding, per-layer checkpoint, final-LayerNorm checkpoint,
  or full-logit memories remain in the production memory contract.
- The LM head visits all 50,257 vocabulary entries and updates only a running
  best value/token; logits are not stored.
- The generated Futil is compiled to SV, synthesized with Yosys, and mapped
  with constrained nextpnr-xilinx for the YPCB target using the proven board
  top-level/clock constraints.
- Reports distinguish mapped FPGA resources from pre-map RTLIL statistics and
  record the first resource or timing failure if the design does not fit.
- No board execution or timing claim is made unless nextpnr completes and the
  timing report passes.

## Scope

This is BRAM-only. DDR3, PCIe, board programming, Representative Core
substitution, and arbitrary-PyTorch generality remain outside this milestone.
