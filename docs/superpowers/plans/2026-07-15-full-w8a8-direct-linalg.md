# Full W8A8 Direct-Linalg No-Handshake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task by
> task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the actual frozen full TinyStories-1M PT2E W8A8 export through
the Direct-Linalg, no-handshake, Calyx route before making a TOSA comparison.

**Architecture:** Register one pipeline alias that reuses the existing
`tinystories-w8a8` model and the already established Direct-Linalg no-handshake
stage package set. The alias intentionally omits the TOSA stage. It does not
modify the model, quantizer, calibration input, or downstream backend passes.

**Tech stack:** PyTorch PT2E/XNNPACK W8A8, Torch-MLIR, MLIR/CIRCT, Calyx, Nix
flakes, Python `unittest`.

## Global Constraints

- Work on user-approved `main`; do not modify or stage the existing
  `docs/glossary.md` change.
- The input model is exactly the existing `tinystories-w8a8` registration:
  full TinyStories-1M checkpoint, frozen single-token-zero-input calibration,
  and XNNPACK PT2E static W8A8 export.
- Use `frontend = "linalg"`, `pipelineStagePackagesNoHandshake`, and
  `noHandshakeLinalgStages`; do not add a TOSA stage or use a TOSA package.
- This is a new full-model resource-scout baseline, not an A/B comparison with
  the explicit-integer micro-slice and not an equivalence or board-validation
  result.
- The existing Calyx pre-lowering pass
  `llm2fpga-lower-scout-math-for-calyx` remains in effect for model name
  `tinystories-w8a8`: it intentionally approximates nonlinear math for a
  provisional resource scout. Record this fact; do not add, remove, or change
  that pass in this task.
- Keep durable evidence in Nix outputs and repository files. Do not run
  `nix gc`, delete store paths, create durable `/tmp` artifacts, or impose an
  arbitrary short cutoff.
- Test first for configuration behavior. If a stage fails, record the first
  factual frontier; do not introduce a speculative lowering workaround.

### Task 1: Expose the full W8A8 Direct-Linalg route

**Files:**

- Modify: `tests/test_full_tinystories_w8a8_scout.py`
- Modify: `flake.nix`

**Interfaces:**

- Consumes: registered model `tinystories-w8a8` and
  `pipelineStagePackagesNoHandshake`.
- Produces: aliases named
  `tinystories-w8a8-via-linalg-no-handshake-<stage>` for each member of
  `noHandshakeLinalgStages`.

- [ ] **Step 1: Write the failing configuration test**

  Add `test_full_model_w8a8_has_public_linalg_no_handshake_alias`. It must find
  alias `tinystories-w8a8-via-linalg-no-handshake` and require all of:

  ```python
  'model = "tinystories-w8a8"'
  'frontend = "linalg"'
  'backend = "calyx-native-sv"'
  'packages = pipelineStagePackagesNoHandshake'
  'stages = noHandshakeLinalgStages'
  ```

  It must reject a TOSA frontend or `pipelineStagePackagesTosaNoHandshake` in
  that alias block.

- [ ] **Step 2: Observe RED**

  Run:

  ```bash
  python3 -m unittest \
    tests.test_full_tinystories_w8a8_scout.FullTinyStoriesW8A8ScoutTest.test_full_model_w8a8_has_public_linalg_no_handshake_alias \
    -v
  ```

  Expected: fail because the alias does not yet exist.

- [ ] **Step 3: Add the alias**

  Add this object alongside the existing full-model no-handshake alias:

  ```nix
  {
    alias = "tinystories-w8a8-via-linalg-no-handshake";
    model = "tinystories-w8a8";
    frontend = "linalg";
    backend = "calyx-native-sv";
    packages = pipelineStagePackagesNoHandshake;
    stages = noHandshakeLinalgStages;
  }
  ```

- [ ] **Step 4: Verify GREEN and commit**

  ```bash
  python3 -m unittest tests.test_full_tinystories_w8a8_scout -v
  nix flake check --no-build
  git diff --check
  git add flake.nix tests/test_full_tinystories_w8a8_scout.py
  git commit -m "feat: add full w8a8 direct linalg route"
  ```

### Task 2: Run the full model through the Direct-Linalg frontier

**Files:**

- Create: `docs/results/2026-07-15-full-w8a8-direct-linalg-scout.md`

**Interfaces:**

- Consumes: Task 1 aliases and the immutable full W8A8 PyTorch export.
- Produces: a factual stage-by-stage result, with no utilization claim unless
  the relevant generated artifact is actually built.

- [ ] **Step 1: Build the frontend stages in order**

  ```bash
  nix build .#tinystories-w8a8-via-linalg-no-handshake-torch -L
  nix build .#tinystories-w8a8-via-linalg-no-handshake-linalg -L
  nix build .#tinystories-w8a8-via-linalg-no-handshake-scf -L
  nix build .#tinystories-w8a8-via-linalg-no-handshake-flat-scf -L
  ```

  Record each immutable output path and inspect `manifest.json`/`blockers.json`
  where applicable.

- [ ] **Step 2: Build Calyx and native SV to the first terminal frontier**

  ```bash
  nix build .#tinystories-w8a8-via-linalg-no-handshake-calyx -L
  nix build .#tinystories-w8a8-via-linalg-no-handshake-calyx-native-sv -L
  ```

  Continue only as far as a generated artifact permits. If either command
  fails, capture its exact error and first failing stage. Do not substitute a
  TOSA route or change nonlinear-math lowering.

- [ ] **Step 3: Write bounded result documentation**

  State the exact package, model provenance, frontend stages, Calyx math-scout
  caveat, completed stages, first failure or generated artifact, commands, and
  what the result does *not* establish. Explicitly distinguish this full W8A8
  baseline from the explicit-integer micro-slice P&R smoke test.

- [ ] **Step 4: Verify and commit**

  ```bash
  python3 -m unittest tests.test_full_tinystories_w8a8_scout -v
  nix flake check --no-build
  git diff --check
  git add docs/results/2026-07-15-full-w8a8-direct-linalg-scout.md
  git commit -m "docs: record full w8a8 direct linalg frontier"
  ```
