# Exact TinyStories Static Subview Memref Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing static-memref-view pass for the one authenticated ranked-static-argument / `memref.subview` interaction, then rerun the exact TinyStories-1M flat-SCF artifact to either produce valid normalized MLIR or capture the next causal frontier.

**Architecture:** First close the one adjudicated evidence-schema residual so the exact frontier object is immutable. Then teach `LowerStaticMemRefViewsForCalyxPass` to model a static, non-rank-reducing subview as an affine view of the already flattened base argument; existing load/store/copy rewrites consume that view, after which dead subviews are erased. Rebuild only the pass plugin, prove the exact affine semantics on the one-operation reproducer and live access probes, and replay the authenticated full artifact without invoking Calyx.

**Tech Stack:** C++ MLIR pass plugin, MemRef dialect, Python `unittest`, Nix, canonical JSON/SHA-256 evidence.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve the exact TinyStories-1M model/package/tokenizer/quantization identities and authenticated Torch, Linalg, SCF, and retained c22 flat-SCF input.
- Change only the existing `llm2fpga-lower-static-memref-views-for-calyx` plugin behavior needed for the exact static, non-rank-reducing `memref.subview` of a flattened ranked argument.
- Do not change Torch-MLIR, shift semantics, model arithmetic, runtime scripts, Nix stage registration, Calyx, DDR3, PCIe, RTL, or board integration.
- Do not generalize to dynamic offsets/sizes/strides, rank-reducing subviews, arbitrary layouts, or unobserved view operations in this plan; unsupported cases remain unchanged and fail closed at verification.
- The exact source signature is `6149b92a9d179ef65caa53ff8dd33259b3d0c05085e5289384627b80c931f693`: `%source: memref<64x64xi64>`, offsets `[0,0]`, sizes `[64,1]`, strides `[1,1]`, result `memref<64x1xi64, strided<[64,1]>>`.
- The semantic mapping for a supported subview is `baseOffset + Σ((offset[d] + index[d] * subviewStride[d]) * baseStride[d])`; the exact signature therefore maps `[i0,i1]` to `64*i0+i1` over `i0∈[0,64)`, `i1∈[0,1)`.
- Do not invoke Calyx unless a later plan has a valid normalized artifact and its registered blocker gate permits it.
- Use test-first development and commit every verified task.

---

### Task 1: Close the Exact Frontier Signature Schema

**Files:**
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py`
- Modify: `tests/test_tinystories_1m_exact_memref_pass.py`
- Modify: `docs/results/2026-08-31-tinystories-1m-exact-memref-pass.md`

**Interfaces:**
- Consumes: Task 3 `compiler_pass_extension` evidence at commit `a0371be`.
- Produces: a closed `earliest_remaining_signature` schema whose inline signature, digest, source location, diagnostic, classification, and reproducer metadata all equal the independently reconstructed `invalid[0]` frontier.

- [ ] **Step 1: Add the final-review mutation as a failing test**

Deep-copy the canonical evaluation, add `registration_claim: true` inside `earliest_remaining_signature.signature`, recompute the top-level canonical self-hash, and require `validate_payload(..., replay=False)` to raise. Add sibling mutations for unknown signature/source-location keys, altered inline signature with a stale digest, altered digest with rebound inline data, and reproducer metadata signature disagreement.

- [ ] **Step 2: Run the focused RED**

```bash
nix develop -c python -m unittest \
  tests.test_tinystories_1m_exact_memref_pass.PublicVerifierTest -v
```

Expected: the nested unknown-key mutation is accepted before the fix.

- [ ] **Step 3: Close and cross-bind the schema**

Add verifier-owned exact key sets for the signature and source-location variants present in the canonical frontier. Recompute the canonical signature JSON and SHA-256 from the independently parsed diagnostic operation, require complete equality with `earliest_remaining_signature.signature`, and require the reproducer sidecar to carry exactly the same operation/signature/digest. Do not rewrite the canonical evaluation if its current object is already valid.

- [ ] **Step 4: Verify and commit**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_pass.py -v
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py \
  tests/test_tinystories_1m_exact_memref_pass.py \
  docs/results/2026-08-31-tinystories-1m-exact-memref-pass.md
git commit -m "fix: close exact memref frontier schema"
```

### Task 2: Model Static Non-Rank-Reducing Subviews

**Files:**
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`
- Create: `tests/test_tinystories_1m_exact_memref_subview_extension.py`
- Create: `reproducers/tinystories-1m-exact-static-subview-extension/identity-offset.mlir`
- Create: `reproducers/tinystories-1m-exact-static-subview-extension/nonzero-offset-stride.mlir`
- Create: `reproducers/tinystories-1m-exact-static-subview-extension/unsupported-rank-reducing.mlir`
- Create: `docs/results/2026-09-01-tinystories-1m-static-subview-extension.md`

**Interfaces:**
- Consumes: `StaticMemRefView`, `getStaticView`, and the exact Task 3 reproducer.
- Produces: `getStaticView(memref::SubViewOp)` support for fully static, non-rank-reducing subviews; dead-subview cleanup after access rewrites.

- [ ] **Step 1: Write semantic RED tests against the current plugin**

Require the current plugin to reproduce the exact `expected 1 offset values, got 2` failure. Add live load/store modules for:

```mlir
// Exact case: linear index = 64*i0+i1.
%view = memref.subview %source[0, 0] [64, 1] [1, 1]
  : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>

// Composition case: linear index = 64 + 128*i0 + 2*i1.
%view = memref.subview %source[1, 0] [16, 8] [2, 2]
  : memref<64x64xi64> to memref<16x8xi64, strided<[128, 2], offset: 64>>
```

The tests must inspect post-pass IR and prove the complete affine coefficient/offset mapping for symbolic indices, not one sample point. Require the rank-reducing and dynamic controls to remain unsupported rather than guessed.

- [ ] **Step 2: Run RED with the existing plugin**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_memref_subview_extension.py -v
```

Expected: exact and composition cases fail verification at the changed argument rank.

- [ ] **Step 3: Implement the narrow view composition**

In `getStaticView`, add a `memref::SubViewOp` branch before the generic memref fallback. Accept only:

- a recursively resolvable source view;
- fully static offsets, sizes, and strides;
- source rank equal to result rank (no dropped dimensions);
- result shape equal to the static sizes;
- result layout consistent with `sourceView.strides[d] * subviewStride[d]` and offset `sourceView.offset + Σ(offset[d] * sourceView.strides[d])`.

Return:

```cpp
StaticMemRefView{
    sourceView->base,
    composedOffset,
    SmallVector<int64_t>(staticSizes),
    composedStrides,
}
```

Collect `memref::SubViewOp` instances in `runOnFunction`, rewrite their transitive loads/stores/copies through the existing recursive view model, and erase only subviews that are use-empty after those rewrites. Do not mutate subview types in place and do not erase a live unsupported subview.

- [ ] **Step 4: Prove GREEN and unsupported behavior**

Build only the pass plugin and run the exact pipeline:

```bash
nix build .#mlir-passes -L
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_memref_subview_extension.py -v
```

Require valid parsed output, no `memref.subview` in the two supported outputs, and exact symbolic mappings `64*i0+i1` and `64+128*i0+2*i1`. Require unsupported rank-reducing/dynamic inputs to remain explicit and never be reported as legalized.

- [ ] **Step 5: Commit**

```bash
git add tools/mlir-passes/FoldConstantTruncFOps.cpp \
  tests/test_tinystories_1m_exact_memref_subview_extension.py \
  reproducers/tinystories-1m-exact-static-subview-extension \
  docs/results/2026-09-01-tinystories-1m-static-subview-extension.md
git commit -m "fix: lower static subviews of flattened memrefs"
```

### Task 3: Replay the Authenticated Full Flat-SCF Artifact

**Files:**
- Create: `scripts/pipeline/evaluate_tinystories_1m_exact_subview_extension.py`
- Create: `scripts/pipeline/verify_tinystories_1m_exact_subview_extension.py`
- Create: `tests/test_tinystories_1m_exact_subview_extension_evaluation.py`
- Create: `artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json`
- Create: `artifacts/comparison/tinystories-1m-exact-subview-extension-evidence/`
- Create: `docs/results/2026-09-01-tinystories-1m-subview-extension-evaluation.md`

**Interfaces:**
- Consumes: authenticated Task 2 contract, Task 3 baseline evaluation, retained c22 flat-SCF input, and the newly built plugin.
- Produces: an authenticated before/after receipt with one of two closed decisions: `valid_normalized_output` or `next_compiler_frontier`.

- [ ] **Step 1: Write evaluation/authentication tests RED**

Require exact immutable input/tool/plugin/pipeline identities, canonical run paths, exact command/exit/stdout/stderr/output replay, and semantic proof replay for the exact and nonzero-offset subview probes. Require the new plugin digest to differ from baseline `6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744`. Reject rebound plugin/input/evidence paths, stale baseline output, unknown schema keys, false valid-output claims, and a claimed next frontier that is not the earliest independently reconstructed diagnostic or residual registered blocker.

- [ ] **Step 2: Run RED**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_subview_extension_evaluation.py -v
```

Expected: evaluator, verifier, receipt, and evidence directory are absent.

- [ ] **Step 3: Execute in causal order**

Run the exact Task 3 one-operation reproducer and both semantic probes first. Only if all pass and their affine proofs match, run the complete 18,933,168-byte retained c22 artifact with:

```text
builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)
```

Preserve exact streams and output. If the command fails or output does not parse, select `next_compiler_frontier` and bind the earliest diagnostic-emitting operation/signature/reproducer. If it parses, independently census all four registered blocker classes and every new invalid class.

- [ ] **Step 4: Apply the closed decision gate**

- Select `valid_normalized_output` only when the full output parses, semantic boundary/access invariants are proven, and no new invalid operation class exists. Record the exact residual registered blocker census; zero blockers is not assumed.
- Otherwise select `next_compiler_frontier`, preserve after counts as unavailable when no valid output exists, and emit exactly one earliest canonical reproducer.
- Do not invoke Calyx or register a Nix stage in either branch.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_subview_extension.py
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_subview_extension_evaluation.py -v
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add scripts/pipeline/evaluate_tinystories_1m_exact_subview_extension.py \
  scripts/pipeline/verify_tinystories_1m_exact_subview_extension.py \
  tests/test_tinystories_1m_exact_subview_extension_evaluation.py \
  artifacts/comparison/tinystories-1m-exact-subview-extension-evaluation.json \
  artifacts/comparison/tinystories-1m-exact-subview-extension-evidence \
  docs/results/2026-09-01-tinystories-1m-subview-extension-evaluation.md
git commit -m "test: replay exact static subview extension"
```

## Follow-Up Rule

- If Task 3 selects `valid_normalized_output`, the next plan starts from its exact residual census: extend only the earliest remaining registered blocker, or register the normalized stage only if the registered blocker count is zero.
- If Task 3 selects `next_compiler_frontier`, the next plan is limited to its one authenticated earliest signature and before/after semantic regression.
- Float-math, Calyx, SystemVerilog, resource, timing, and board work remain ineligible until a valid normalized flat-SCF artifact with zero registered memref blockers exists.
