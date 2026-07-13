# Full TinyStories PT2E W8A8 Scout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose and run a reproducible full-TinyStories XNNPACK PT2E W8A8 pipeline through TOSA, no-handshake Calyx SystemVerilog, and Yosys statistics, with provisional graph and build evidence.

**Architecture:** Reuse the checked-in `TinyStories/model_adapter_pt2e_static_quant.py`; register one full-model W8A8 model and route it through the existing TOSA/no-handshake pipeline. Package the post-PT2E FX graph audit as non-gating evidence, then run the public Yosys-stat target under the existing build monitor and write a checked-in scout report from the observed artifacts and logs.

**Tech Stack:** Nix flakes, PyTorch PT2E/XNNPACK, Torch-MLIR, TOSA, MLIR/CIRCT Calyx, SystemVerilog, Yosys, Python `unittest`.

## Global Constraints

- Work directly on `main`, as explicitly authorized by the user.
- Reuse the existing XNNPACK PT2E implementation; do not add SmoothQuant or a new quantizer.
- Use full TinyStories-1M, not the representative core.
- Use the existing TOSA/no-handshake pipeline and generate SV plus Yosys statistics.
- Defer simulation, equivalence, board validation, and place-and-route.
- Label all scout resource evidence provisional.

---

### Task 1: Register the full-model W8A8 pipeline

**Files:**
- Modify: `nix/models.nix`
- Modify: `flake.nix`
- Test: `tests/test_full_tinystories_w8a8_scout.py`

**Interfaces:**
- Consumes: `TinyStories/model_adapter_pt2e_static_quant.py`, `registerTosaNoHandshakeModel`, `noHandshakeStages`.
- Produces: model `tinystories-w8a8` and aliases `tinystories-w8a8-via-tosa-no-handshake-{torch,tosa,linalg,scf,flat-scf,calyx,calyx-native-sv,calyx-sv,il,yosys-stat}`.

- [ ] **Step 1: Write a failing registration test**

Add assertions that `nix/models.nix` registers `tinystories-w8a8` with `pt2e-static-w8a8`, the full-model PT2E adapter, the TinyStories snapshot, and `pythonWithTinyStoriesTorchAO`; assert that `flake.nix` exports the TOSA/no-handshake alias through `noHandshakeStages`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest tests.test_full_tinystories_w8a8_scout -v`

Expected: FAIL because `tinystories-w8a8` and its alias are absent.

- [ ] **Step 3: Add the minimal model and alias definitions**

Register the full checkpoint with the existing adapter and add one `pipelineAliasSpecs` entry using `pipelineStagePackagesTosaNoHandshake` and `noHandshakeStages`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python3 -m unittest tests.test_full_tinystories_w8a8_scout -v`

Expected: PASS.

- [ ] **Step 5: Verify Nix evaluation and commit**

Run: `nix eval .#packages.x86_64-linux.tinystories-w8a8-via-tosa-no-handshake-yosys-stat.name`

Expected: a derivation name ending in `tinystories-w8a8-yosys-stat`.

Commit: `feat: register full TinyStories W8A8 scout`

### Task 2: Package the non-gating PT2E graph audit

**Files:**
- Create: `scripts/pipeline/pt2e_graph_shape_audit.py`
- Modify: `flake.nix`
- Modify: `tests/test_full_tinystories_w8a8_scout.py`

**Interfaces:**
- Consumes: `tinystories-w8a8-pytorch-exported/graph.txt`.
- Produces: package `tinystories-w8a8-pt2e-graph-shape-audit` containing `report.json` and `report.md`; exits successfully even when float/QDQ blockers are found.

- [ ] **Step 1: Write failing audit behavior and package tests**

Test a synthetic QDQ-wrapped float matmul and require `status=fail`, `float_matmul_after_dequant`, operation counts, and Markdown output. Assert the flake package consumes the full-model exported graph and does not pass `--fail-on-nonstructural`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest tests.test_full_tinystories_w8a8_scout -v`

Expected: FAIL because the script and package do not exist.

- [ ] **Step 3: Port the minimal provenance audit**

Port `/home/roland/LLM2FPGA/scripts/task6/pt2e_graph_shape_audit.py` under `scripts/pipeline/`, retaining JSON/Markdown output and non-gating behavior.

- [ ] **Step 4: Add the audit derivation**

Wire the script to `pipelineStagePackages."tinystories-w8a8-pytorch-exported"/graph.txt`, produce both reports, and export the package.

- [ ] **Step 5: Run focused and regression tests, then commit**

Run: `python3 -m unittest tests.test_full_tinystories_w8a8_scout tests.test_pipeline_clarity -v`

Expected: PASS.

Commit: `feat: package PT2E W8A8 graph audit`

### Task 3: Run and record the provisional scout

**Files:**
- Create: `docs/results/2026-07-13-full-tinystories-pt2e-w8a8-scout.md`
- Create when available: `artifacts/full-tinystories-pt2e-w8a8-scout/`

**Interfaces:**
- Consumes: audit package and `tinystories-w8a8-via-tosa-no-handshake-yosys-stat`.
- Produces: durable command, timing, stage frontier, artifact-size, graph-audit, and Yosys-resource evidence; failures are recorded at the first failing stage.

- [ ] **Step 1: Build the graph audit**

Run: `nix build .#tinystories-w8a8-pt2e-graph-shape-audit --no-link --print-out-paths -L`

Expected: package succeeds and reports structural pass/fail without gating.

- [ ] **Step 2: Run the monitored Yosys-stat build**

Run the public target with `/usr/bin/time -v` and `scripts/pipeline/monitor_build.sh`, retaining logs beneath `/tmp` until copied into the result bundle.

Expected: either Yosys statistics are produced or the first failing stage is identified with elapsed time and peak RSS.

- [ ] **Step 3: Inspect and copy bounded evidence**

Copy only compact JSON/Markdown/stat/log summaries into `artifacts/full-tinystories-pt2e-w8a8-scout/`; do not copy giant MLIR/SV files into Git.

- [ ] **Step 4: Write the provisional result report**

Record commands, toolchain/package identities, graph audit, stage sizes, elapsed time, peak RSS, first failure or Yosys metrics, and the explicit statement that equivalence was deferred.

- [ ] **Step 5: Run final verification and commit**

Run: `python3 -m unittest discover -s tests -v`

Run: `nix flake check --no-build`

Run: `git status --short`

Expected: tests pass, flake evaluates, and only intended report/artifact changes remain before commit.

Commit: `docs: record full TinyStories W8A8 scout`
