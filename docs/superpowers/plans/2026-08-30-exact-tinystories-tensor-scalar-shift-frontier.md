# Exact TinyStories Tensor-Scalar Shift Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the exact authenticated TinyStories-1M program beyond its proven Torch-MLIR `Tensor_Scalar` arithmetic-right-shift frontier, verify the change semantically, and capture the next earliest causal compiler frontier.

**Architecture:** Add one narrowly scoped Torch-MLIR frontend legalization, packaged by Nix against the pinned Torch-MLIR revision, before `torchdynamo-export-to-torch-backend-pipeline` rejects the generic operator. The legalization accepts only signed-si64 tensor/scalar shifts with constant counts 0 through 62, broadcasts the count, and preserves arithmetic-shift semantics. Existing provenance-bound producer/verifier scripts then authenticate the reduced reproducer and the full registered model stage before the normal pipeline is rerun sequentially.

**Tech Stack:** Nix flakes, pinned Torch-MLIR/MLIR C++, MLIR pass plugins or a minimal pinned-source patch, Python `unittest`, torch.export, CIRCT/Calyx, SystemVerilog.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve `roneneldan/TinyStories-1M` revision `ac533fb8b4f69c71894bf96badfe11e6294d9fcf` and every Task 1--3 identity recorded in `artifacts/comparison/tinystories-1m-exact-frontier-decision.json`.
- Do not modify the model adapter, quantization, fixed-point arithmetic, tokenizer, package, frozen prompt, or frozen 16-token result.
- Do not use the Representative Core or introduce DDR3, PCIe, board integration, custom RTL, or scheduling changes.
- Accept only `!torch.vtensor<...,si64>` shifted by a compile-time scalar integer in `[0,62]`; use sign-preserving arithmetic right shift and preserve shape and width.
- Reject negative counts as `shift_contract:negative_shift` and counts above 62 as `shift_contract:greater_than_sixty_two`; never mask the count.
- Keep ties-away fixed-point rounding separate from bitwise shifting.
- Every compiler stage must either yield a nonempty hash-bound valid artifact or become the new earliest causal frontier with a deterministic receipt and minimal reproducer.
- Use test-first development and commit every verified task.

---

### Task 1: Torch-MLIR Tensor-Scalar Shift Legalization

**Files:**
- Create: `patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch` or `tools/torch-mlir-passes/LegalizeBitwiseRightShiftTensorScalar.cpp`
- Create when using a plugin: `tools/torch-mlir-passes/CMakeLists.txt`
- Create when using a plugin: `nix/torch-mlir-passes.nix`
- Modify: `torch-mlir.nix` only if the pinned-source patch is the smallest working insertion point
- Modify: `flake.nix`
- Modify: `nix/pipeline.nix`
- Create: `tests/test_tinystories_1m_exact_shift_legalization.py`

**Interfaces:**
- Consumes: the exact generic operator and types in `reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir`.
- Produces: a pinned `torch-mlir-opt` route in which the legalization runs immediately before `torchdynamo-export-to-torch-backend-pipeline`; its public registered stage remains `tiny-stories-1m-kev-gpt-exact-torch`.

- [ ] **Step 1: Write structural red tests**

Add tests that require the Nix expression to build the legalization against the pinned Torch-MLIR ABI, require its pass to precede the backend pipeline, and reject any edit to `TinyStories/model_adapter_exact_package.py`. Add source assertions for the exact operator spelling, signed-si64 type checks, constant count bounds, arithmetic right shift, scalar broadcast, and failure signaling.

- [ ] **Step 2: Run the structural tests and reproduce the compiler failure**

Run:

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_shift_legalization.py -v
nix develop -c torch-mlir-opt -pass-pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=})' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir -o /dev/null
```

Expected: the new tests fail because the legalization is absent; the reproducer exits 1 with the accepted illegal-`torch.operator` diagnostic.

- [ ] **Step 3: Implement the smallest valid frontend legalization**

Prefer a loadable pass plugin when it can run before the failing backend pipeline without rebuilding CIRCT. If Torch-MLIR does not expose the required dialect/link interface to an external plugin, record that evidence in the task report and use a minimal patch to the pinned Torch-MLIR source instead. Match only `torch.aten.bitwise_right_shift.Tensor_Scalar` with a signed-si64 value tensor and a constant scalar count, materialize a same-shape shift tensor or equivalent elementwise representation, and lower through Torch-MLIR to arithmetic `arith.shrsi`. Emit the two contract diagnostics for invalid constants and fail on dynamic counts or any other dtype.

- [ ] **Step 4: Run the reduced and full-stage green tests**

Run the structural tests, the exact reproducer through the packaged tool and pipeline, and:

```bash
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
```

Expected: every command exits 0, the reduced output contains no matching generic `torch.operator`, the registered artifact is nonempty, and Task 1--3 identity files remain byte-identical.

- [ ] **Step 5: Commit**

```bash
git add patches/torch-mlir tools/torch-mlir-passes nix/torch-mlir-passes.nix torch-mlir.nix flake.nix nix/pipeline.nix tests/test_tinystories_1m_exact_shift_legalization.py
git commit -m "feat: legalize exact signed tensor scalar shifts"
```

Stage only paths that exist for the selected plugin-or-patch implementation.

### Task 2: Provenance-Bound Semantic Executor

**Files:**
- Create: `scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py`
- Modify: `scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py` only if the real compiler executor exposes a previously unrepresented binding
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py` only to validate a newly required binding, never to relax an existing one
- Modify: `tests/test_tinystories_1m_exact_frontier_semantics.py`
- Create: `artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json`

**Interfaces:**
- Consumes: the packaged stage/tool from Task 1 and `artifacts/comparison/tinystories-1m-exact-shift-semantics.json`.
- Produces: `tinystories-1m-exact-shift-executor-results-v1` and a canonical self-hashed, provenance-bound semantic probe accepted by the existing verifier.

- [ ] **Step 1: Add failing executor tests**

Require the executor to run the selected compiler artifact rather than Python’s `>>`, bind stage/tool/pipeline/fixture hashes, return exactly the five fixture case IDs, preserve signed-si64 shapes and values for valid cases, and return the exact rejection statuses/diagnostics with no output for invalid cases. Add negative tests for a detached stage, altered tool, altered pipeline, duplicate case, extra case, and missing case.

- [ ] **Step 2: Confirm the tests fail because the executor is absent**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier_semantics.py -v
```

Expected: failure naming the missing executor or missing compiler-backed case evidence.

- [ ] **Step 3: Implement the compiler-backed executor**

Parse the fixture, generate one MLIR module per case using the exact `Tensor_Scalar` operation and signed-si64 tensor shape, invoke the packaged tool with the pinned pass pipeline, and execute the lowered arithmetic using the compiler route selected in Task 1. Validate the compiler output and derive results from it; do not calculate accepted outputs with a detached Python shift. For invalid cases, require compiler rejection and normalize only the two exact contract diagnostics.

- [ ] **Step 4: Produce and verify the authenticated report**

```bash
nix develop -c python scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py --executor scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py --out artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py --probe-report artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier_semantics.py -v
```

Expected: all commands pass and the report binds the live registered stage derivation, exact tool bytes, exact pipeline, fixture, producer, executor, decision, and Task 1--3 identities.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py tests/test_tinystories_1m_exact_frontier_semantics.py artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
git commit -m "test: prove exact signed shift compiler semantics"
```

### Task 3: Authenticated Pipeline Rerun and Next Frontier

**Files:**
- Modify: `scripts/pipeline/classify_tinystories_1m_exact_frontier.py`
- Modify: `tests/test_tinystories_1m_exact_frontier.py`
- Modify: `artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json`
- Modify: `docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md`
- Create: a classifier-named directory under `reproducers/` whose name is the exact `first_invalid_stage` value when a later stage fails

**Interfaces:**
- Consumes: the Task 1 registered Torch stage and Task 2 semantic proof.
- Produces: either valid hash-bound artifacts through `calyx-native-sv`, or a deterministic receipt for the first later invalid stage with its minimal reproducer.

- [ ] **Step 1: Add the semantic gate to the frontier runner tests**

Require classification to refuse a pipeline rerun unless Task 2’s report verifies against current bytes. Require strictly sequential stage execution, stopping after the first invalid stage, and require two byte-identical classification bundles for the same frontier.

- [ ] **Step 2: Run the classifier tests red**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier.py -v
```

Expected: failure because the runner does not yet require the new semantic proof.

- [ ] **Step 3: Wire the new proof and rerun the registered pipeline**

Update the runner to verify Task 2 first, then execute `pytorch-exported`, `torch`, `linalg`, `scf`, `flat-scf`, `calyx`, and `calyx-native-sv` in order. Never execute a later stage after an invalid artifact. Preserve the original stage commands, constraints, model, and identities.

- [ ] **Step 4: Minimize and authenticate the observed frontier**

If a later stage fails, reduce only the failing operation/pattern while retaining the exact types and diagnostic, store the full failing input and logs, run the classifier twice, and require byte-identical receipts. If all stages pass, validate the emitted SystemVerilog with the registered syntax/synthesis check and record its content hash; do not claim board inference.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier.py -v
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
scripts/agent/pre_final_check.sh
git add scripts/pipeline/classify_tinystories_1m_exact_frontier.py tests/test_tinystories_1m_exact_frontier.py artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md reproducers
git commit -m "test: capture next exact compiler frontier"
```

Expected: tests and determinism verification pass; the commit contains either valid synthesizable SV evidence or exactly one newly established earliest frontier.

## Follow-Up Rule

If Task 3 finds a later frontier rather than valid synthesizable SystemVerilog, write a new bounded plan from that receipt before changing the compiler again. Repeat this evidence-backed loop without changing the active goal or its frozen model contract until `calyx-native-sv` is valid and synthesizable.
