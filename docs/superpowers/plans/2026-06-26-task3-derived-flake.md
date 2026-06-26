# Task3 Derived Flake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a reduced Nix flake for the latest working Task 3-derived MLIR-to-SV pipeline embedded in `~/LLM2FPGA` branch `task6-crisp`.

**Architecture:** Keep the reusable Task 3 pipeline scripts and Nix pipeline constructor intact, then define a small model registry for smoke, FP32, and W4A8 bring-up targets. The flake exposes per-stage packages so failures can be isolated at `torch`, `linalg`, `cf`, `handshake`, `hw`, `sv`, and Yosys stages.

**Tech Stack:** Nix flakes, torch-mlir, MLIR, CIRCT, Yosys with slang, PyTorch export, PT2E static quantization.

---

### Task 1: Import Task 3-Derived Sources

**Files:**
- Copy: `scripts/pipeline/`
- Copy: `scripts/compile-pytorch.py`
- Copy: `scripts/direct_lower.py`
- Copy: `nix/pipeline.nix`
- Copy: `nix/nanobind-bootstrap.nix`
- Copy: `patches/circt-upstream-task3-recovery/`
- Copy: `patches/torch-mlir-task3-rfp/`
- Copy: `patches/torch-mlir-task6/`
- Copy: `torch-mlir.nix`
- Copy: `rtl/fp/circt_fp_primitives.sv`

- [x] Copy the current `task6-crisp` Task 3-derived pipeline files.
- [x] Remove copied generated `__pycache__` directories.

### Task 2: Add Reduced Flake

**Files:**
- Create: `flake.nix`
- Create: `nix/models.nix`

- [x] Define only compiler bring-up inputs, excluding Task 6 board and PCIe inputs.
- [x] Preserve the current CIRCT Task 3 recovery patch set.
- [x] Preserve the current torch-mlir source build and default to the same unpatched torch-mlir selection used by `task6-crisp`.
- [x] Expose `matmul`, `tinystories-fp32`, `tinystories-representative-core-fp32`, and `tinystories-representative-core-w4a8` stage packages.

### Task 3: Verify Evaluation

**Files:**
- Read: `flake.nix`
- Read: `nix/models.nix`

- [x] Run `nix flake show`.
- [x] Build `.#model-registry`.
- [x] Build `.#matmul-torch`.
- [x] Build `.#matmul-linalg`.
- [x] Build `.#tinystories-representative-core-w4a8-torch`.
- [x] Build `.#tinystories-representative-core-w4a8-linalg`.
