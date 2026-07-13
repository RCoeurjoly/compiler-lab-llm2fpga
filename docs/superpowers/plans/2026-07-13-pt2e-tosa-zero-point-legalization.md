# PT2E TOSA Zero-Point Legalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Legalize only PT2E-generated narrow TOSA zero-point additions, validate the legalized TOSA boundary, and advance the full TinyStories W8A8 no-handshake pipeline to its next measured frontier.

**Architecture:** Extend the checked-in MLIR pass plugin with a structural TOSA rewrite instead of patching Torch-MLIR or editing MLIR text. The TOSA-to-Linalg stage loads the plugin, runs the narrow legalization, validates TOSA, and only then invokes standard TOSA lowering.

**Tech Stack:** C++17, MLIR 21 TOSA pass plugin API, Nix derivations, Python `unittest`, shell pipeline scripts.

## Global Constraints

- Work and commit directly on `main`.
- Match only the complete PT2E zero-point scaffold defined in the approved design.
- Leave arbitrary or ambiguous `i8 tosa.add` operations unchanged.
- Preserve the existing public pipeline aliases.
- Defer functional equivalence, board validation, and SmoothQuant.

---

### Task 1: Executable regression for the legalization contract

**Files:**
- Create: `reproducers/pt2e-tosa-zero-point/input.mlir`
- Create: `reproducers/pt2e-tosa-zero-point/unrelated-add.mlir`
- Modify: `tests/test_full_tinystories_w8a8_scout.py`

**Interfaces:**
- Consumes: the pass name `llm2fpga-legalize-pt2e-tosa-zero-point` from the design.
- Produces: positive and negative MLIR fixtures plus repository assertions used by the pass and pipeline tasks.

- [ ] **Step 1: Write failing tests**

Add tests requiring the fixture files, pass registration, TOSA dialect linkage, plugin loading, legalization-before-validation ordering, and preservation of the unrelated-add fixture.

- [ ] **Step 2: Verify RED**

Run:

```sh
python3 -m unittest tests.test_full_tinystories_w8a8_scout -v
```

Expected: failure because the pass registration and pipeline invocation do not exist.

- [ ] **Step 3: Add minimal fixtures**

The positive fixture contains the exact `f32 -> i8 cast`, splat zero-point `tosa.const`, `i8 tosa.add`, and sole `i8 -> i32 cast` sequence. The negative fixture contains an `i8 tosa.add` on function arguments with no PT2E provenance.

- [ ] **Step 4: Re-run the focused tests**

Expected: fixture checks pass while implementation checks remain red.

- [ ] **Step 5: Commit the regression**

```sh
git add reproducers/pt2e-tosa-zero-point tests/test_full_tinystories_w8a8_scout.py
git commit -m "test: reproduce PT2E TOSA zero-point add"
```

### Task 2: Implement the narrow MLIR pass

**Files:**
- Create: `tools/mlir-passes/LegalizePt2eTosaZeroPoint.cpp`
- Modify: `tools/mlir-passes/CMakeLists.txt`
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`

**Interfaces:**
- Consumes: ranked TOSA tensors matching the approved provenance and single-use contract.
- Produces: registered module pass `--llm2fpga-legalize-pt2e-tosa-zero-point`.

- [ ] **Step 1: Add the pass implementation**

Walk `tosa::AddOp` operations and require `i8` ranked operands/result, one float-producing `tosa::CastOp`, and one splat `tosa::ConstOp`. Do not constrain the number or kind of consumers. Create an `i32` cast, `i32` zero-point constant, `i32 tosa.add`, and identity `tosa.rescale` from `i32` to `i8`, then replace only the original add result. The rescale provides profile-valid saturating narrowing because TOSA rejects `i32 tosa.clamp`.

- [ ] **Step 2: Register and link the pass**

Add the source to `LLM2FPGAMLIRPasses`, link `MLIRTosaDialect`, declare a registration function in the new source, and invoke it from the existing plugin callback.

- [ ] **Step 3: Build the plugin**

Run:

```sh
nix build .#llm2fpgaMlirPasses --no-link --print-out-paths -L
```

Expected: the plugin builds successfully.

- [ ] **Step 4: Execute positive and negative fixtures**

Run the pinned MLIR `mlir-opt` with `--load-pass-plugin`, the new pass, and `--tosa-validate`. Expected: the positive fixture validates and contains an `i32 tosa.add`; the negative fixture remains an `i8 tosa.add` and validation fails.

- [ ] **Step 5: Run focused repository tests and commit**

```sh
python3 -m unittest tests.test_full_tinystories_w8a8_scout -v
git add tools/mlir-passes tests/test_full_tinystories_w8a8_scout.py
git commit -m "feat: legalize PT2E TOSA zero-point additions"
```

### Task 3: Integrate legalization and validation at the TOSA boundary

**Files:**
- Modify: `scripts/pipeline/tosa_to_linalg.sh`
- Modify: `nix/pipeline.nix`
- Modify: `tests/test_quantized_linalg_diagnostics.py`

**Interfaces:**
- Consumes: `${llm2fpgaMlirPasses}/lib/LLM2FPGAMLIRPasses.so` and raw TOSA.
- Produces: validated, legalized input to `--tosa-to-linalg-pipeline`.

- [ ] **Step 1: Write a failing pipeline-order test**

Require the script to load the plugin and order:

```text
llm2fpga-legalize-pt2e-tosa-zero-point
tosa-validate
tosa-to-linalg-pipeline
```

- [ ] **Step 2: Verify RED**

Run the focused diagnostics test and confirm it fails because the script lacks the plugin and passes.

- [ ] **Step 3: Update the script and Nix derivation**

Pass the plugin path explicitly from `mkTosaToLinalgDerivation`, load it in `tosa_to_linalg.sh`, run legalization and validation before standard lowering, and include `llm2fpgaMlirPasses` in the derivation inputs.

- [ ] **Step 4: Verify the previous frontier is crossed**

Run:

```sh
nix build .#tinystories-w8a8-linalg --no-link --print-out-paths -L
```

Expected: no failure on the recognized zero-point `i8 tosa.add`; any failure must identify a different operation or an unmatched pattern.

- [ ] **Step 5: Commit integration**

```sh
git add scripts/pipeline/tosa_to_linalg.sh nix/pipeline.nix tests/test_quantized_linalg_diagnostics.py
git commit -m "feat: validate legalized TOSA before Linalg"
```

### Task 4: Rerun the full scout and record the next frontier

**Files:**
- Modify: `docs/results/2026-07-13-full-tinystories-pt2e-w8a8-scout.md`
- Modify: `artifacts/full-tinystories-pt2e-w8a8-scout/result.json`
- Modify as evidence requires: `docs/current-baseline.md`

**Interfaces:**
- Consumes: `tinystories-w8a8-via-tosa-no-handshake-yosys-stat`.
- Produces: durable status, timing, artifact-size, and resource/frontier evidence.

- [ ] **Step 1: Run the monitored full build**

```sh
scripts/pipeline/monitor_build.sh /tmp/full-tinystories-w8a8-legalized-scout 5 -- \
  nix build .#tinystories-w8a8-via-tosa-no-handshake-yosys-stat \
  --no-link --print-out-paths -L
```

- [ ] **Step 2: Classify the result**

If Yosys succeeds, record resource statistics. Otherwise record the last successful stage, first failing operation, wall time, sampled peak memory, and available artifact sizes. Do not report downstream stages as reached when they were not.

- [ ] **Step 3: Update durable evidence**

Record that the old narrow-add frontier was fixed, the number of rewritten/missed illegal additions if available, and the new frontier without claiming equivalence.

- [ ] **Step 4: Run full verification**

```sh
python3 -m unittest discover -s tests -v
python3 -m json.tool artifacts/full-tinystories-pt2e-w8a8-scout/result.json >/dev/null
nix flake check --no-build
git diff --check
```

- [ ] **Step 5: Commit evidence**

```sh
git add docs/results docs/current-baseline.md artifacts/full-tinystories-pt2e-w8a8-scout/result.json
git commit -m "docs: record legalized W8A8 pipeline frontier"
```
