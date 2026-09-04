# Exact TinyStories Direct Rank-One Copy Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lower the remaining direct static rank-one alloc-to-alloc `memref.copy` operations, then replay the exact TinyStories-1M flat-SCF artifact and determine whether normalized flat-SCF reaches zero registered memref blockers.

**Architecture:** Remove the one evidence-proven early-return case only for distinct direct `memref.alloc` bases with equal positive static rank-one shape. Reuse the existing `emitCopyLoopNest` lowering so copy semantics become an explicit `scf.for`, flattened source load, and target store. Preserve all aliasing, dynamic, non-alloc, rank-zero, mismatched, and unsupported cases. Replay from immutable c22 and, only if zero registered blockers is independently proven, hand off to a separate stage-registration/pre-Calyx plan.

**Tech Stack:** C++ MLIR pass plugin, MemRef/SCF/Arith dialects, Python `unittest`, Nix, canonical JSON/SHA-256 evidence.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve the exact TinyStories-1M identities, immutable c22 input SHA-256 `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`, and reviewed plugin behavior through commit `83391e9`.
- The exact first residual is `memref.copy %alloc_379, %alloc_381 : memref<1xi64> to memref<1xi64>` at normalized-output line 8,832; both values are direct static `memref.alloc` definitions.
- Support only distinct direct `memref.alloc` bases, equal element type, equal positive static rank-one shape `[N]`, identity/static stride-one views, and no dynamic metadata.
- Preserve semantics `for i in [0,N): target[i] = source[i]`, with source-load and target-store roles and bounds proven independently.
- Do not lower same-base or potentially aliasing copies, rank-zero copies, dynamic shapes, different shapes/types/layouts, globals, function arguments, calls, or unknown allocation-like values in this plan.
- Preserve all reviewed subview/collapse/reinterpret, root-use, call-boundary, symbol-resolution, fixpoint, and checked-arithmetic behavior.
- Do not modify runtime scripts, Nix stage registration, Calyx, RTL, model arithmetic, DDR3, PCIe, or board integration.
- Use test-first development and commit every verified task.

---

### Task 1: Lower Distinct Static Rank-One Alloc Copies

**Files:**
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`
- Create: `tests/test_tinystories_1m_exact_direct_rank1_copy.py`
- Create: `reproducers/tinystories-1m-exact-direct-rank1-copy/size1.mlir`
- Create: `reproducers/tinystories-1m-exact-direct-rank1-copy/size64.mlir`
- Create: `reproducers/tinystories-1m-exact-direct-rank1-copy/unsupported-alias.mlir`
- Create: `docs/results/2026-09-01-tinystories-1m-direct-rank1-copy.md`

**Interfaces:**
- Consumes: `rewriteCopy`, `StaticMemRefView`, and `emitCopyLoopNest`.
- Produces: explicit loop lowering for the exact direct static alloc-to-alloc rank-one case.

- [ ] **Step 1: Write semantic and safety REDs**

For `memref<1xi64>` and `memref<64xi64>` distinct allocations, require post-pass output to contain one loop with bounds `[0,N)`, source load from the first allocation, target store to the second, and no `memref.copy`. Include live initialization/observation so direction is provable. Add REDs/controls for same-base copy, dynamic alloc, mismatched sizes, rank zero, non-identity layout, function-argument bases, global bases, and copy whose source/target may alias through a view.

- [ ] **Step 2: Run RED against the reviewed plugin**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_direct_rank1_copy.py -v
```

Expected: size-1 and size-64 direct alloc copies remain as `memref.copy`; unsupported controls remain unchanged.

- [ ] **Step 3: Replace the early return with a narrow eligibility gate**

In `rewriteCopy`, keep the existing general view-copy lowering. For the current direct rank-at-most-one early return, lower only when both `sourceView->base` and `targetView->base` are the original operands, both defining operations are distinct `memref::AllocOp`, both memref types are static rank one with the same positive shape and element type, and both views have offset 0 and stride `[1]`. Otherwise retain the early return.

For an eligible copy, call the existing `emitCopyLoopNest` with shape `[N]` and erase the copy only after the loop/load/store is created. Do not special-case `N=1` into combinational assignment; the common loop is the semantic reference.

- [ ] **Step 4: Prove GREEN and regress prior pass behavior**

```bash
nix build .#llm2fpgaMlirPasses -L
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_direct_rank1_copy.py \
  tests/test_tinystories_1m_exact_strided_unit_collapse.py \
  tests/test_tinystories_1m_exact_memref_subview_extension.py -v
```

Require exact loop bounds, source/target base identity and roles, stride-one index formula, no copy in supported outputs, explicit copies in unsupported outputs, valid parsing, and all previous compiler regressions green.

- [ ] **Step 5: Commit**

```bash
git add tools/mlir-passes/FoldConstantTruncFOps.cpp \
  tests/test_tinystories_1m_exact_direct_rank1_copy.py \
  reproducers/tinystories-1m-exact-direct-rank1-copy \
  docs/results/2026-09-01-tinystories-1m-direct-rank1-copy.md
git commit -m "fix: lower exact direct rank one copies"
```

### Task 2: Replay Full TinyStories and Evaluate the Zero-Blocker Gate

**Files:**
- Create: `scripts/pipeline/evaluate_tinystories_1m_exact_rank1_copy_extension.py`
- Create: `scripts/pipeline/verify_tinystories_1m_exact_rank1_copy_extension.py`
- Create: `tests/test_tinystories_1m_exact_rank1_copy_extension_evaluation.py`
- Create: `artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evaluation.json`
- Create: `artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evidence/`
- Create: `docs/results/2026-09-01-tinystories-1m-rank1-copy-extension-evaluation.md`

**Interfaces:**
- Consumes: authenticated unit-collapse receipt/output, immutable c22, pinned tool, and rebuilt plugin.
- Produces: an exact valid output or next frontier plus a closed `zero_registered_blockers` boolean.

- [ ] **Step 1: Write absent-surface/authentication REDs**

Require exact prior receipt/output, c22, tool, plugin/source, pipeline, canonical causal order, paths, commands, streams, generic censuses, registered counts, and semantic copy proofs. Reject rehashed mutations, false source/target direction, wrong loop bounds, stale outputs, after-only classes, false zero claims, and branch-incompatible stage-registration fields.

- [ ] **Step 2: Run RED**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_rank1_copy_extension_evaluation.py -v
```

Expected: evaluator, verifier, receipt, evidence directory, and report are absent.

- [ ] **Step 3: Replay size-1 and size-64 probes, then full c22**

Prove loop domain, stride-one index, distinct bases, source-load/target-store direction, and live observation for both probes. Then run full c22 with the exact pipeline, parse output, and produce complete generic operation and registered blocker censuses.

- [ ] **Step 4: Apply the closed gate**

- `zero_registered_blockers: true` requires exit/parse success, no after-only operation class, semantic proofs, and exact zero counts for collapse/copy/expand/reinterpret.
- If any registered blocker remains, bind the earliest source-order blocker plus defining chain as the next frontier.
- Zero registered blockers does not itself authorize Calyx; record the exact artifact/hash for a separate registration and pre-Calyx legality plan.
- Do not run Calyx or register a Nix stage here.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_rank1_copy_extension.py
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_rank1_copy_extension_evaluation.py -v
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add scripts/pipeline/evaluate_tinystories_1m_exact_rank1_copy_extension.py \
  scripts/pipeline/verify_tinystories_1m_exact_rank1_copy_extension.py \
  tests/test_tinystories_1m_exact_rank1_copy_extension_evaluation.py \
  artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evaluation.json \
  artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evidence \
  docs/results/2026-09-01-tinystories-1m-rank1-copy-extension-evaluation.md
git commit -m "test: replay exact direct rank one copy extension"
```

## Follow-Up Rule

- If zero registered blockers is proven, the next plan registers the exact normalized artifact and runs only pre-Calyx legality before any Calyx lowering.
- Otherwise the next plan targets only the authenticated earliest residual pair.
- Calyx, SystemVerilog, synthesis, timing, and board work remain pending until the registered stage and pre-Calyx legality gates pass.
