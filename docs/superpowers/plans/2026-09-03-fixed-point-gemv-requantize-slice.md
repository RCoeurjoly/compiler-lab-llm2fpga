# Exact Fixed-Point GEMV-Requantize Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Prove exact TinyStories-1M `GEMV -> requantize` semantics through a project-owned fixed-point schema and generated Calyx trace.

**Architecture:** Capture the real 4-row frozen-prompt boundary fixture; legalize it to verified `llm2fpga.fixed` schema operations, then lower logical SSA to explicit Calyx storage/control.

**Spec:** docs/adr/2026-09-03-exact-fixed-point-vertical-slices.md

## Global Constraints

- Exact TinyStories-1M fixed-point contract; no RC as acceptance, DDR3, PCIe, generic SCF, or copied RTL.
- Each command is capped at 1800 seconds; semantic authority is frozen PyTorch.

### Task 1: Capture and verify contract fixture

**Files:** Create fixture capture/probe and exact-output tests under `TinyStories/` and `tests/`.

- [ ] Write a failing test requiring a named frozen-prompt 4x64 input, exact GEMV result, and exact requantized output hashes.
- [ ] Capture the real first crossing inputs/outputs from the authenticated exact model; bind package, source, prompt, tensor bytes, and hashes in a self-hashed receipt.
- [ ] Verify eager replay bit-exactly, commit `feat: capture fixed point requantize fixture`.

### Task 2: Fixed-point schema contract pass

**Files:** Create an out-of-tree pass and tests under `tools/torch-mlir-passes/` and `tests/`.

- [ ] Write failing tests for `fixed.requantize` attributes: scale, rounding, signedness, saturation, width; reject missing or altered attributes.
- [ ] Legalize only the captured GEMV-to-requantization chain into generic MLIR schema operations with logical SSA operands/results.
- [ ] Verify schema evaluation hashes equal Task 1, commit `feat: legalize fixed point requantize schema`.

### Task 3: Calyx lowering and acceptance gate

**Files:** Create fixed-schema Calyx lowerer, trace verifier, and tests under `scripts/pipeline/` and `tests/`.

- [ ] Write failing tests requiring logical SSA to map to explicit generated memories/control, ordered-value trace equality, and rejection of an altered rounding rule.
- [ ] Generate Calyx/SV only from the schema; run bounded simulation and compare ordered trace plus output hashes to Task 1.
- [ ] Run Yosys syntax/stat and all slice tests; commit `feat: lower exact fixed point requantize slice`.
