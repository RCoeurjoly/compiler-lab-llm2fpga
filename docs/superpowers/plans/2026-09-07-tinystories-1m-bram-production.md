# Plan: TinyStories-1M BRAM-only production architecture

**Spec:** `docs/superpowers/specs/2026-09-07-tinystories-1m-bram-production-design.md`

## Task 1 — Define the production memory contract

Add a compiler-owned production variant that removes audit checkpoint
memories, retains only live activations/parameters/state, and streams the
LM-head argmax. Add tests proving no full-logit or audit checkpoint preload is
possible while the oracle token contract remains authoritative.

## Task 2 — Verify production generated SV

Compile the production Futil to SV and run the bounded two-token simulation.
Compare selected tokens, feedback contexts, final live outputs, reset/restart,
and source-only preload against the validated oracle.

## Task 3 — Synthesize and map for YPCB

Run Yosys and constrained nextpnr-xilinx with the proven YPCB top-level and
clock/XDC constraints. Record mapped LUT/FF/BRAM/DSP use, timing, logs,
tool/source hashes, and the first failure if placement or routing cannot
complete.

## Global constraints

- Preserve the validated fixed-point arithmetic and parameter layout.
- Do not use DDR3 or PCIe.
- Every compiler, simulation, synthesis, and P&R stage has an explicit
  deadline and durable diagnostic artifact.
