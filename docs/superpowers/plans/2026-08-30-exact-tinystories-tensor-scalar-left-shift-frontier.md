# Exact TinyStories Tensor-Scalar Left-Shift Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the authenticated TinyStories-1M Torch-MLIR `torch.aten.bitwise_left_shift.Tensor_Scalar` frontier without changing model semantics, then capture the next earliest compiler frontier.

**Architecture:** First freeze signed-si64 left-shift behavior with executable PyTorch and MLIR cases, including discarded high bits and invalid counts. Then extend the existing pinned Torch-MLIR source patch with a separate narrow legalization immediately before `torch-reduce-op-variants`, rerun the full registered model, and either produce a valid Torch artifact or a deterministic successor frontier receipt.

**Tech Stack:** PyTorch, Nix flakes, pinned Torch-MLIR/MLIR C++, Python `unittest`, deterministic provenance receipts.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve the exact model, adapter, package, tokenizer, quantization, fixed-point profile, prompt, frozen 16-token result, and Task 1--3 hashes.
- Preserve the accepted right-shift legalization and its historical and successor receipts.
- Match only `torch.aten.bitwise_left_shift.Tensor_Scalar` on identical signed-si64 value-tensor input/result types and direct constant scalar counts in `[0,62]`.
- Preserve PyTorch signed-si64 two's-complement bit behavior: shift left, discard bits above bit 63, reinterpret the remaining 64 bits as signed; do not saturate or widen the observable result.
- Reject negative, greater-than-62, dynamic, and non-si64 shifts with named contract diagnostics and no output.
- Do not modify the model adapter or implement unrelated operators, custom RTL, scheduling, DDR3, PCIe, or board integration.
- Stop at the first later invalid compiler stage and record it deterministically; do not run cascading later stages.
- Use test-first development and commit every verified task.

---

### Task 1: Freeze Exact Signed Left-Shift Semantics

**Files:**
- Create: `artifacts/comparison/tinystories-1m-exact-left-shift-semantics.json`
- Create: `scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py`
- Create: `tests/test_tinystories_1m_exact_left_shift_semantics.py`
- Create: `docs/results/2026-08-30-tinystories-1m-exact-left-shift-semantics.md`

**Interfaces:**
- Consumes: the exact model adapter and `reproducers/tinystories-1m-exact-torch-mlir/bitwise-left-shift-tensor-scalar.mlir`.
- Produces: canonical self-hashed semantic cases and a verifier binding them to live PyTorch, the exact reproducer, the successor receipt, and Task 1--3 identities.

- [ ] **Step 1: Write failing fixture/verifier tests**

Require case IDs for shift zero, the model-observed shift 16, a negative operand, positive and negative high-bit discard/wrap, shift 62, negative count, count 63, dynamic count, and si32 rejection. Valid cases must preserve dtype and shape; invalid cases must have exact statuses and no output.

- [ ] **Step 2: Run red tests**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_left_shift_semantics.py -v
```

Expected: fail because the fixture and independent verifier do not exist.

- [ ] **Step 3: Materialize the authenticated semantic fixture**

Run each valid signed-si64 case through live pinned PyTorch `torch.bitwise_left_shift`, serialize exact decimal outputs, dtype, and shape, and independently recompute the expected 64-bit result as `unsigned = (value & ((1 << 64) - 1)); shifted = (unsigned << count) & ((1 << 64) - 1); signed = shifted - (1 << 64) if shifted & (1 << 63) else shifted`. Bind PyTorch version/binary, reproducer bytes, successor receipt, adapter, and Task 1--3 hashes. Invalid cases are contract requirements for the compiler pass and must not be presented as PyTorch execution results.

- [ ] **Step 4: Verify and commit**

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py
nix develop -c python -m unittest tests/test_tinystories_1m_exact_left_shift_semantics.py -v
git add artifacts/comparison/tinystories-1m-exact-left-shift-semantics.json scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py tests/test_tinystories_1m_exact_left_shift_semantics.py docs/results/2026-08-30-tinystories-1m-exact-left-shift-semantics.md
git commit -m "test: freeze exact signed left shift semantics"
```

Expected: verifier and tests pass and the artifact is canonical/self-hashed.

### Task 2: Legalize Left Shift and Capture the Next Frontier

**Files:**
- Modify: `patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch` (rename to `legalize-bitwise-shift-tensor-scalar.patch` if the Nix patch path and all provenance bindings are migrated atomically)
- Modify: `torch-mlir.nix`
- Create: `tests/test_tinystories_1m_exact_left_shift_legalization.py`
- Modify: `scripts/pipeline/capture_tinystories_1m_exact_successor_frontier.py`
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_successor_frontier_determinism.py`
- Create: a versioned successor receipt and two capture bundles under `artifacts/comparison/`
- Create: a minimal reproducer under `reproducers/tinystories-1m-exact-torch-mlir/` if a later operation fails

**Interfaces:**
- Consumes: Task 1's semantic fixture, the accepted right-shift patch, and `tiny-stories-1m-kev-gpt-exact-torch`.
- Produces: valid tensor/tensor Torch left-shift lowering with verified `arith.shli`, plus either a nonempty registered Torch artifact or a deterministic next-frontier receipt.

- [ ] **Step 1: Write the legalization red tests**

Require a distinct left-shift matcher, identical signed-si64 tensor types, direct constant bounds `[0,62]`, scalar tensor materialization and broadcast, rewrite to registered `torch.aten.bitwise_left_shift.Tensor`, exact invalid-count/type diagnostics, and generated Linalg containing `arith.shli`. Require the existing right-shift tests to remain green.

- [ ] **Step 2: Reproduce the accepted left-shift failure**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_left_shift_legalization.py -v
nix develop -c torch-mlir-opt -pass-pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=})' reproducers/tinystories-1m-exact-torch-mlir/bitwise-left-shift-tensor-scalar.mlir -o /dev/null
```

Expected: tests fail because the legalization is absent; the reproducer exits 1 at the accepted generic operator.

- [ ] **Step 3: Implement the narrow pinned-source legalization**

Add a separate pass or separately named rewrite adjacent to the accepted right-shift pass. Convert the scalar constant to a rank-zero signed-si64 tensor, broadcast it to the input shape, replace only the exact generic left-shift operator with registered tensor/tensor left shift, and fail closed with exact diagnostics for unsupported inputs. Do not reuse arithmetic-right-shift behavior or alter the adapter.

- [ ] **Step 4: Run reduced semantic and full-model gates**

```bash
nix build --no-link --print-out-paths -L .#torchMlir
nix develop -c python -m unittest tests/test_tinystories_1m_exact_shift_legalization.py tests/test_tinystories_1m_exact_left_shift_legalization.py tests/test_tinystories_1m_exact_left_shift_semantics.py -v
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
```

Expected for the reduced path: exact cases match Task 1 and generated Linalg uses `arith.shli`. The full-stage command may either succeed with a nonempty artifact or fail only at a distinct later operation.

- [ ] **Step 5: Authenticate the result and commit**

If the full stage succeeds, create two independently generated byte-identical success receipts binding the artifact, derivation, tool, patch, commands, Task 1 fixture, prior receipts, and Task 1--3 identities. If it fails, archive the complete failing input/log, minimize the first later operation, prove interestingness, and create two byte-identical self-hashed successor receipts; list every later stage as not run.

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_successor_frontier_determinism.py
scripts/agent/pre_final_check.sh
git add patches/torch-mlir torch-mlir.nix tests/test_tinystories_1m_exact_left_shift_legalization.py scripts/pipeline/capture_tinystories_1m_exact_successor_frontier.py scripts/pipeline/verify_tinystories_1m_exact_successor_frontier_determinism.py artifacts/comparison reproducers/tinystories-1m-exact-torch-mlir
git commit -m "feat: legalize exact signed tensor scalar left shifts"
```

## Follow-Up Rule

After review, resume Task 2 of `2026-08-30-exact-tinystories-tensor-scalar-shift-frontier.md` only if the registered Torch stage is valid. Otherwise write the next bounded plan from the newly authenticated frontier before changing compiler behavior.
