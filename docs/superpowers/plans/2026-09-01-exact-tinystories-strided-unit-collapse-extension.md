# Exact TinyStories Strided Unit-Collapse Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lower the authenticated static rank-2 `N×1` strided `memref.collapse_shape` over a supported subview, then replay the exact TinyStories-1M flat-SCF artifact to produce the next valid normalized output or one new causal frontier.

**Architecture:** Extend the existing recursive `StaticMemRefView` model with one algebraically exact collapse case: `memref<N×1×T, strided<[S,1], offset:O>>` collapsed by `[[0,1]]` into `memref<N×T, strided<[S], offset:O>>`. Loads, stores, and copies already consume the resulting base/offset/stride view, so supported collapse/subview chains can be erased after their uses are rewritten. Rebuild only the plugin and replay from the immutable retained c22 input; do not invoke Calyx.

**Tech Stack:** C++ MLIR pass plugin, MemRef dialect, Python `unittest`, Nix, canonical JSON/SHA-256 evidence.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve the exact TinyStories-1M model/package/tokenizer/quantization identities, retained c22 flat-SCF input SHA-256 `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`, and reviewed static-subview plugin behavior at commit `226bfc2`.
- The exact first pair is full normalized-output lines 2,586–2,587: a `memref<64x64xi64>` subview `[0,0] [64,1] [1,1]` producing `memref<64x1xi64, strided<[64,1]>>`, then `collapse_shape [[0,1]]` producing `memref<64xi64, strided<[64]>>`.
- Support only static rank-2 `N×1`, source-view strides `[S,1]`, reassociation exactly `[[0,1]]`, rank-1 result shape `[N]`, and result offset/stride exactly `[O]/[S]`.
- Preserve the complete semantic map `O + S*i` for `i∈[0,N)`. Offset and stride arithmetic remain checked and fail closed.
- Do not generalize arbitrary collapse reassociations, non-unit trailing dimensions, dynamic shapes/layouts, or rank changes beyond 2→1 in this plan.
- Do not modify model arithmetic, Torch-MLIR, runtime scripts, Nix stage registration, Calyx, RTL, DDR3, PCIe, or board integration.
- A valid output with residual blockers is not Calyx eligibility; measure and follow its exact next causal pair.
- Use test-first development and commit every verified task.

---

### Task 1: Lower Static Strided `N×1 → N` Collapse Views

**Files:**
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`
- Create: `tests/test_tinystories_1m_exact_strided_unit_collapse.py`
- Create: `reproducers/tinystories-1m-exact-strided-unit-collapse/offset-zero.mlir`
- Create: `reproducers/tinystories-1m-exact-strided-unit-collapse/offset-nonzero.mlir`
- Create: `reproducers/tinystories-1m-exact-strided-unit-collapse/unsupported-nonunit.mlir`
- Create: `docs/results/2026-09-01-tinystories-1m-strided-unit-collapse.md`

**Interfaces:**
- Consumes: the reviewed `StaticMemRefView` subview composition and full normalized artifact SHA-256 `42d682b642b899b10bc0814a7786a5803d69b839148e79bbfdc803425e261f34`.
- Produces: recursive `getStaticView(memref::CollapseShapeOp)` support for exactly the static strided unit-trailing-dimension case.

- [ ] **Step 1: Write exact semantic REDs**

Create live load/store probes for:

```mlir
// O=0, S=64: linear index 64*i.
%sub = memref.subview %source[0, 0] [64, 1] [1, 1]
  : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
%flat = memref.collapse_shape %sub [[0, 1]]
  : memref<64x1xi64, strided<[64, 1]>>
    into memref<64xi64, strided<[64]>>

// O=7, S=64: linear index 7+64*i.
%sub = memref.subview %source[0, 7] [64, 1] [1, 1]
  : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: 7>>
%flat = memref.collapse_shape %sub [[0, 1]]
  : memref<64x1xi64, strided<[64, 1], offset: 7>>
    into memref<64xi64, strided<[64], offset: 7>>
```

Independently reconstruct the complete emitted affine DAG and require base argument 0, domains `[0,64)`, offsets `0/7`, and coefficient `[64]`. Add controls for trailing dimension 2, wrong result stride/offset, dynamic metadata, non-`[[0,1]]` reassociation, and mixed supported/unsupported siblings; none may flatten a root that leaves invalid live views.

- [ ] **Step 2: Run RED against the reviewed plugin**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_strided_unit_collapse.py -v
```

Expected: the exact collapse/subview chains remain explicit because the current collapse branch requires identity source strides.

- [ ] **Step 3: Implement the exact algebraic case**

In `getStaticView(memref::CollapseShapeOp)`, retain the existing identity-layout path. Add a second path only when:

- `sourceView->shape == [N,1]` with positive static `N`;
- `sourceView->strides == [S,1]` with positive static `S`;
- the collapse reassociation is exactly one group `[0,1]`;
- the result is rank 1, shape `[N]`, with extractable static layout offset `O` and stride `S` equal to `sourceView->offset` and `sourceView->strides[0]`.

Return the same underlying base with offset `O`, shape `[N]`, and stride `[S]`. Reuse checked arithmetic and the existing dependency-fixpoint preflight. Do not reinterpret a non-unit dimension as contiguous and do not change the result type in place.

- [ ] **Step 4: Prove GREEN, composition, copy, and rejection**

```bash
nix build .#llm2fpgaMlirPasses -L
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_strided_unit_collapse.py \
  tests/test_tinystories_1m_exact_memref_subview_extension.py -v
```

Require the two supported outputs to parse with no subview/collapse, exact formulas `64*i` and `7+64*i`, and supported source/target collapsed-copy chains to lower to flattened load/store loops. Every unsupported control must remain explicit with its root rank preserved or fail MLIR input verification before the pass.

- [ ] **Step 5: Commit**

```bash
git add tools/mlir-passes/FoldConstantTruncFOps.cpp \
  tests/test_tinystories_1m_exact_strided_unit_collapse.py \
  reproducers/tinystories-1m-exact-strided-unit-collapse \
  docs/results/2026-09-01-tinystories-1m-strided-unit-collapse.md
git commit -m "fix: lower exact strided unit collapses"
```

### Task 2: Replay the Exact Full Artifact and Select the Next Pair

**Files:**
- Create: `scripts/pipeline/evaluate_tinystories_1m_exact_unit_collapse_extension.py`
- Create: `scripts/pipeline/verify_tinystories_1m_exact_unit_collapse_extension.py`
- Create: `tests/test_tinystories_1m_exact_unit_collapse_extension_evaluation.py`
- Create: `artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json`
- Create: `artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence/`
- Create: `docs/results/2026-09-01-tinystories-1m-unit-collapse-extension-evaluation.md`

**Interfaces:**
- Consumes: authenticated prior subview-extension receipt/output, immutable retained c22 input, pinned tool, and newly rebuilt plugin.
- Produces: exact before/after full operation census, registered blocker census, semantic probe proofs, and one closed decision: `valid_normalized_output` or `next_compiler_frontier`.

- [ ] **Step 1: Write the absent-surface and authentication REDs**

Require evaluator, verifier, receipt, evidence directory, and report. Require exact bindings for the prior receipt/output, c22 input, tool, new plugin, pass source commit/blob, pipeline, canonical run order/paths/commands/streams, and complete generic operation censuses. Reject stale plugin/output, rebound evidence, unknown schema fields, false semantic proof, false blocker counts, a new after-only operation class, and a next-pair claim not independently derived from the earliest residual def-use pair.

- [ ] **Step 2: Run RED**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_unit_collapse_extension_evaluation.py -v
```

Expected: five required production/evidence surfaces are absent.

- [ ] **Step 3: Execute causal probes, then full c22**

Run offset-zero, offset-nonzero, and collapsed-copy probes first with the exact pipeline:

```text
builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)
```

Only after their complete affine/base/role/domain proofs pass, run the 18,933,168-byte retained c22 artifact. Preserve and replay exact pass/parse/generic-print commands and streams.

- [ ] **Step 4: Apply the closed decision**

- Select `valid_normalized_output` only for exit 0, parseable output, proven scoped semantics, and no after-only operation class. Record exact residual counts for all operations and the four registered blocker classes.
- Otherwise select `next_compiler_frontier`, with unavailable after counts when no valid output exists and one exact earliest diagnostic reproducer.
- For valid output with residual blockers, derive the next causal pair from the earliest residual registered blocker and its defining view chain; do not choose by class count or assume standalone behavior.
- Never invoke Calyx or register the stage in this task.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_unit_collapse_extension.py
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_unit_collapse_extension_evaluation.py -v
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add scripts/pipeline/evaluate_tinystories_1m_exact_unit_collapse_extension.py \
  scripts/pipeline/verify_tinystories_1m_exact_unit_collapse_extension.py \
  tests/test_tinystories_1m_exact_unit_collapse_extension_evaluation.py \
  artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evaluation.json \
  artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence \
  docs/results/2026-09-01-tinystories-1m-unit-collapse-extension-evaluation.md
git commit -m "test: replay exact strided unit-collapse extension"
```

## Follow-Up Rule

- If the registered blocker count reaches zero and the output remains valid, write a separate stage-registration/pre-Calyx legality plan; do not invoke Calyx implicitly.
- Otherwise write the next plan for only the independently derived earliest residual registered blocker plus its defining view chain and semantic regression.
- Calyx, SystemVerilog, resource, timing, and board gates remain pending until normalized flat-SCF has zero registered blockers and passes the pre-Calyx legality census.
