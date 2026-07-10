# Task 3 Main Representative-Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build FTS and RC with the exact `main` Task 3 closure and report their utilization comparison.

**Architecture:** Preserve commit `b6dc8ab` as a nested locked flake, add RC at its model and wrapper boundaries, and re-export its packages from the root flake. Both utilization reports are consumed by one non-gating comparison derivation.

**Tech Stack:** Nix flakes, PyTorch/torch-mlir, CIRCT, SystemVerilog, Yosys/yosys-slang, Python report generation.

## Global Constraints

- Do not collect or judge timing.
- Add no unit-test package; derivation evaluation and live builds are the verification surface.
- Emit final report artifacts only from utilization and comparison packages.
- Preserve the Task 3 wrapper behavior; adapt RC ports only as its generated SV requires.
- Thresholds are reported manually and never fail the build.

---

### Task 1: Preserve the Task 3 closure

**Files:**
- Create: `task3-main/`
- Modify: `flake.nix`

- [ ] Copy commit `b6dc8ab` source and lockfile into `task3-main/`.
- [ ] Add `task3-main-pipeline` as a root path input without dependency follows.
- [ ] Re-export the nested FTS package from the root package surface.
- [ ] Run `nix flake show --all-systems` and confirm the root package evaluates.

### Task 2: Add RC to the exact pipeline

**Files:**
- Modify: `task3-main/nix/models.nix`
- Modify: `task3-main/flake.nix`
- Create: `task3-main/TinyStories/model_adapter_representative_core.py`
- Create: `task3-main/scripts/pipeline/gen_tiny_stories_selftest_top.py`

- [ ] Register RC using the old direct Task 3 compile command and approved shape.
- [ ] Generate RC's wrapper from its Task 3 `main.sv` interface.
- [ ] Feed RC RTLIL and the generated wrapper into the unchanged Task 3 model optimization, memory externalization, and nine synthesis stages.
- [ ] Re-export the RC utilization package from the root package surface.
- [ ] Build the root RC utilization package and inspect its three reports.

### Task 3: Compare FTS and RC

**Files:**
- Modify: `task3-main/flake.nix`
- Create: `task3-main/scripts/pipeline/compare_task3_representative_core_parity.py`
- Create: `task3-main/representative-core-parity-shapes.json`

- [ ] Add a report derivation consuming the live FTS and RC summaries.
- [ ] Report LUT/FF reduction thresholds and model shape ratios without a failing assertion.
- [ ] Re-export the comparison package from the root package surface.
- [ ] Build the root comparison package and inspect all report values.

### Task 4: Verify and commit

**Files:**
- Modify: `flake.lock`

- [ ] Confirm nested and root lock resolution uses the copied Task 3 pins.
- [ ] Build FTS, RC, and parity from the root package names.
- [ ] Review `git diff --check` and `git status`.
- [ ] Commit all scoped changes.
