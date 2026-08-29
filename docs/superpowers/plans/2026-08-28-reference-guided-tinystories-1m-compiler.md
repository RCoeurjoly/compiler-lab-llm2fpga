# Exact-input TinyStories-1M Compiler Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run an authenticated executable representation of the exact kev-gpt TinyStories-1M model through the unchanged LLM2FPGA compiler pipeline and capture its first causal frontier.

**Architecture:** Establish one hash-bound source of truth for model, package, tokenizer, quantization, and integer semantics. Prove an exact PyTorch/exported-program implementation against the kev-gpt oracle before registering it as a compiler model; then run the existing Torch-MLIR, Linalg/SCF, CIRCT/Calyx, and SystemVerilog stages without backend substitutions. Stop at and document the first invalid or behavior-changing boundary.

**Tech Stack:** Python 3.11 and PyTorch inside Nix, Hugging Face Transformers, torch.export, Torch-MLIR, MLIR, CIRCT/Calyx, SystemVerilog, repository JSON receipts, SHA-256.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Scope is the frozen TinyStories-1M configuration, not arbitrary PyTorch models or other TinyStories sizes.
- The input must use the exact package at `/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m` and fail closed if any hash differs.
- Run Python only through `nix develop -c python` or a Nix derivation.
- Before the first frontier is captured, change only the authenticated input adapter, provenance wiring, model registration, tests, and receipts.
- Do not add external RTL primitives, nonlinear approximations, custom scheduling, DDR3, PCIe, or board-shell changes.
- Partial compiler output following a diagnostic is invalid.
- Each task begins and ends with `scripts/agent/pre_final_check.sh` and one verified commit.
- If an authority required for exact semantics is missing, commit a user-approved diagnostic checkpoint rather than inventing semantics.

---

### Task 1: Authenticate the exact executable contract

**Files:**
- Create: `scripts/comparison/audit_tinystories_1m_exact_input.py`
- Create: `tests/test_tinystories_1m_exact_input_audit.py`
- Create: `artifacts/reference/tinystories-1m-exact-input-audit.json`
- Create: `artifacts/reference/tinystories-1m-exact-input-contract.json`
- Modify: `scripts/comparison/verify_tinystories_1m_reference_input.py`
- Inspect: `scripts/comparison/authenticate_tinystories_1m_qdq_semantics.py`
- Inspect: `/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m/{manifest.json,receipt.json,weights.bin,scales.bin,calibration_ids.bin}`

**Interfaces:**
- Consumes: `audit_exact_input(contract_path: Path, package_path: Path, kev_root: Path) -> dict[str, object]`.
- Produces: schema `tinystories-1m-exact-input-audit-v1` with `status` equal to `authenticated` or `identity_frontier`, exact hashes, source revision/patch identity, resolved semantics, and `conflicts`.

- [x] **Step 1: Write a failing audit test for the known activation-granularity contradiction**

```python
def test_audit_rejects_the_old_per_tensor_contract():
    result = audit_exact_input(CONTRACT, PACKAGE, KEV_ROOT)
    assert result["activation_quantization"]["scale_vector_count"] == 97
    assert result["contract"]["activation_granularity"] == "per_channel"
    assert result["conflicts"] == []
```

- [x] **Step 2: Verify the test fails for the current contract**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_input_audit.py -v`

Expected: FAIL because the current contract says `per-tensor` and lacks a complete executable-semantics authority.

- [x] **Step 3: Implement the fail-closed audit**

Parse and hash every package file, validate tensor offset ranges and overlaps, count and shape all activation-scale vectors, record the Hugging Face revision, record `git rev-parse HEAD` plus the relevant kev-gpt working-tree diff hash, and compare the package generator/reference semantics with the contract. Emit `identity_frontier` with named conflicts when two authorities disagree.

- [x] **Step 4: Correct only fields established by authoritative evidence**

Create a versioned exact-input contract with the package-observed granularity and explicit fields for scale application, accumulator width, rounding, saturation, overflow, LayerNorm, Softmax, GELU, and token selection only when the audit can cite their source path and SHA-256. Preserve the historical contract and its SHA-bound receipts unchanged. Leave unresolved fields absent and report them as conflicts; do not choose values heuristically.

- [x] **Step 5: Run the audit tests and canonical audit**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_input_audit.py tests/test_tinystories_1m_reference_input.py tests/test_tinystories_1m_reference_contract.py -v`

Run: `nix develop -c python scripts/comparison/audit_tinystories_1m_exact_input.py --contract artifacts/reference/tinystories-1m-exact-input-contract.json --package /home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m --kev-root /home/roland/kev-gpt/.worktrees/kintex-selftest --output artifacts/reference/tinystories-1m-exact-input-audit.json`

Expected: either `authenticated` with no conflicts or a precise `identity_frontier`. Task 2 is forbidden unless status is `authenticated`.

- [x] **Step 6: Commit the identity gate**

```bash
git add scripts/comparison/audit_tinystories_1m_exact_input.py tests/test_tinystories_1m_exact_input_audit.py artifacts/reference/tinystories-1m-exact-input-audit.json artifacts/reference/tinystories-1m-exact-input-contract.json
git commit -m "authenticate exact TinyStories compiler input"
```

### Task 2: Build an exact quantized PyTorch model

**Files:**
- Create: `TinyStories/model_adapter_exact_package.py`
- Create: `tests/test_tinystories_1m_exact_package_model.py`
- Create: `artifacts/reference/tinystories-1m-exact-package-model.json`
- Reuse: `TinyStories/model_adapter_reference_package.py`

**Interfaces:**
- Consumes: Task 1 audit with `status == "authenticated"`.
- Produces: `load_exact_model(contract_path: Path, package_path: Path, model_path: Path) -> ExactModelBundle` and `export_exact_program(bundle: ExactModelBundle) -> torch.export.ExportedProgram`.
- `ExactModelBundle.model(input_ids: Tensor) -> Tensor` returns authenticated fixed-point logits for a context of at most 32 tokens.

- [ ] **Step 1: Write failing tests for exact arithmetic and fail-closed identity**

```python
def test_exact_model_matches_frozen_block_zero_checkpoints():
    bundle = load_exact_model(CONTRACT, PACKAGE, MODEL)
    trace = bundle.trace(torch.tensor([[7454, 2402, 257, 640]]))
    assert trace["trace_sha256"] == FROZEN_TRACE_SHA256

def test_exact_model_rejects_non_authenticated_audit():
    with self.assertRaisesRegex(ExactModelError, "identity_frontier"):
        load_exact_model(CONFLICTING_CONTRACT, PACKAGE, MODEL)
```

- [ ] **Step 2: Verify tests fail because no exact adapter exists**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_package_model.py -v`

Expected: FAIL importing `model_adapter_exact_package`.

- [ ] **Step 3: Implement package-bound quantized execution**

Reuse authenticated tensor reconstruction but execute the Task 1 semantics explicitly at every named Q/DQ boundary. Keep integer codes, scale application, accumulation, rounding, and saturation observable. Do not delegate these rules to default PyTorch quantization behavior.

- [ ] **Step 4: Export and replay the exact program**

Export the logits-only forward using the frozen prompt shape, replay `exported.module()`, and compare every named block-0 checkpoint and final logits hash against eager execution.

- [ ] **Step 5: Verify exact-model tests**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_package_model.py tests/test_tinystories_1m_package_adapter.py -v`

Expected: PASS with the exact package, and rejection after mutating any package hash or arithmetic field.

- [ ] **Step 6: Commit the exact adapter**

```bash
git add TinyStories/model_adapter_exact_package.py tests/test_tinystories_1m_exact_package_model.py artifacts/reference/tinystories-1m-exact-package-model.json
git commit -m "add exact TinyStories package model"
```

### Task 3: Prove frozen generation equivalence before lowering

**Files:**
- Create: `scripts/comparison/verify_tinystories_1m_exact_generation.py`
- Create: `tests/test_tinystories_1m_exact_generation.py`
- Create: `artifacts/reference/tinystories-1m-exact-generation.json`

**Interfaces:**
- Consumes: `ExactModelBundle`, prompt IDs `[7454, 2402, 257, 640]`, and the frozen 16-token sequence.
- Produces: `verify_generation(bundle, prompt_ids, expected_tokens, count=3) -> dict[str, object]` with per-step logits hashes, selected token IDs, checkpoint hashes, and repeated-run hashes.

- [ ] **Step 1: Write a failing exact-generation test**

```python
def test_three_runs_match_the_frozen_sequence():
    result = verify_generation(BUNDLE, [7454, 2402, 257, 640], EXPECTED, count=3)
    assert result["status"] == "matched"
    assert [run["tokens"] for run in result["runs"]] == [EXPECTED] * 3
```

- [ ] **Step 2: Verify the missing harness fails**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_generation.py -v`

Expected: FAIL importing the verifier.

- [ ] **Step 3: Implement deterministic greedy generation**

For each token, run the exact model with the current context, hash the authenticated fixed-point logits, select the smallest token ID among equal maxima, append it, and stop after 16 tokens. Repeat three times in fresh model instances.

- [ ] **Step 4: Compare eager and exported execution**

Require both execution modes to produce identical per-step logits hashes, checkpoint hashes, and tokens. Report the first token/checkpoint mismatch and do not register the compiler model on failure.

- [ ] **Step 5: Run focused verification**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_generation.py -v`

Expected: PASS and an `exact-generation` receipt bound to the Task 1 and Task 2 hashes.

- [ ] **Step 6: Commit the generation gate**

```bash
git add scripts/comparison/verify_tinystories_1m_exact_generation.py tests/test_tinystories_1m_exact_generation.py artifacts/reference/tinystories-1m-exact-generation.json
git commit -m "prove exact TinyStories generation input"
```

### Task 4: Register the exact model without changing the backend

**Files:**
- Modify: `nix/models.nix`
- Modify: `flake.nix`
- Create: `tests/test_tinystories_1m_exact_pipeline_registration.py`

**Interfaces:**
- Consumes: `TinyStories/model_adapter_exact_package.py` and canonical Task 1–3 receipts.
- Produces: model key `tiny-stories-1m-kev-gpt-exact` using the existing pipeline stage constructors and a package-aware exported-program derivation.

- [ ] **Step 1: Write a failing registration test**

```python
def test_exact_model_uses_existing_pipeline_and_canonical_package():
    registration = load_registration("tiny-stories-1m-kev-gpt-exact")
    assert registration["backend_overrides"] == []
    assert registration["package_manifest_sha256"] == EXPECTED_MANIFEST_SHA256
```

- [ ] **Step 2: Verify the model key is absent**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_pipeline_registration.py -v`

Expected: FAIL because `tiny-stories-1m-kev-gpt-exact` is not registered.

- [ ] **Step 3: Add the package-aware Nix registration**

Use the existing `registerModel` stage graph. The exported command must pass explicit contract, package, and model paths and must verify Task 1–3 receipt hashes before writing `exported.pt2`. Do not add passes or alter shared pipeline scripts.

- [ ] **Step 4: Evaluate registration and build only the export stage**

Run: `nix eval .#packages.x86_64-linux.tiny-stories-1m-kev-gpt-exact-pytorch-exported.name`

Run: `nix build .#tiny-stories-1m-kev-gpt-exact-pytorch-exported -L`

Expected: the export derivation succeeds with a manifest bound to the exact-input audit and generation receipt.

- [ ] **Step 5: Run registration tests**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_pipeline_registration.py -v`

- [ ] **Step 6: Commit the registration**

```bash
git add nix/models.nix flake.nix tests/test_tinystories_1m_exact_pipeline_registration.py
git commit -m "register exact TinyStories compiler model"
```

### Task 5: Run the unchanged pipeline and capture its first frontier

**Files:**
- Create: `scripts/pipeline/classify_tinystories_1m_exact_frontier.py`
- Create: `tests/test_tinystories_1m_exact_frontier.py`
- Create: `artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json`
- Create: `docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md`

**Interfaces:**
- Consumes: the registered stage outputs and logs for `pytorch-exported`, `torch-mlir`, `linalg`, `scf`, `flat-scf`, `calyx`, and `calyx-native-sv`.
- Produces: `classify_frontier(stage_records: list[StageRecord]) -> FrontierReceipt`, using the statuses defined by the spec and naming the earliest invalid stage only.

- [ ] **Step 1: Write failing classifier tests**

```python
def test_classifier_reports_the_earliest_invalid_stage():
    result = classify_frontier([valid("torch_mlir"), invalid("calyx", "math.exp"), invalid("sv", "cascade")])
    assert result.frontier == "calyx_frontier"
    assert result.diagnostic == "math.exp"
```

- [ ] **Step 2: Verify the classifier is absent**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier.py -v`

- [ ] **Step 3: Implement strict stage validation and hashing**

Require each successful stage to have a nonempty artifact, SHA-256, command, tool revision, and zero terminal diagnostic. Reject partial Calyx output when its log contains an unhandled operation even if the process exits zero.

- [ ] **Step 4: Build stages sequentially until the first failure**

Run each target in order, stopping after the first invalid stage:

```bash
nix build .#tiny-stories-1m-kev-gpt-exact-torch-mlir -L
nix build .#tiny-stories-1m-kev-gpt-exact-linalg -L
nix build .#tiny-stories-1m-kev-gpt-exact-scf -L
nix build .#tiny-stories-1m-kev-gpt-exact-flat-scf -L
nix build .#tiny-stories-1m-kev-gpt-exact-calyx -L
nix build .#tiny-stories-1m-kev-gpt-exact-calyx-native-sv -L
```

- [ ] **Step 5: Generate the frontier receipt and minimal reproducer**

Run: `nix develop -c python scripts/pipeline/classify_tinystories_1m_exact_frontier.py --model tiny-stories-1m-kev-gpt-exact --output artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json`

Extract the smallest IR retaining the same diagnostic when the failing stage supports reduction. Record both full-artifact and reproducer hashes.

- [ ] **Step 6: Verify and commit the frontier**

Run: `nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier.py -v`

```bash
git add scripts/pipeline/classify_tinystories_1m_exact_frontier.py tests/test_tinystories_1m_exact_frontier.py artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md reproducers/
git commit -m "record exact TinyStories compiler frontier"
```

### Task 6: Select the next change from the observed frontier

**Files:**
- Create: `docs/results/2026-08-29-tinystories-1m-exact-frontier-decision.md`
- Create: `artifacts/comparison/tinystories-1m-exact-frontier-decision.json`
- Modify: `docs/working-notes.org`

**Interfaces:**
- Consumes: Task 5 frontier and reproducer.
- Produces: one ranked next action with `frontier_hash`, rejected alternatives, expected observable improvement, regression command, and scope boundary.

- [ ] **Step 1: Compare the frontier against the four permitted response classes**

Classify the response as exactly one of `compiler_pass`, `bit_accurate_primitive`, `scheduling_or_memory_architecture`, or `autoregressive_runtime_boundary`. Cite the failing operation/structure and explain why each rejected class does not address that causal boundary.

- [ ] **Step 2: Define the next regression before implementation**

Record the exact command and expected before/after result. The regression must retain all Task 1–3 identity and generation hashes.

- [ ] **Step 3: Validate decision binding**

Run: `nix develop -c python -m json.tool artifacts/comparison/tinystories-1m-exact-frontier-decision.json`

Verify that `frontier_hash` equals the on-disk Task 5 receipt hash and that only one response class is selected.

- [ ] **Step 4: Commit the decision checkpoint**

```bash
git add docs/results/2026-08-29-tinystories-1m-exact-frontier-decision.md artifacts/comparison/tinystories-1m-exact-frontier-decision.json docs/working-notes.org
git commit -m "select next exact-input compiler change"
```

This plan ends at the evidence-backed decision gate. Implementing the selected
compiler or architecture change requires a follow-up plan because its files,
tests, and acceptance criteria depend on the frontier observed in Task 5.
