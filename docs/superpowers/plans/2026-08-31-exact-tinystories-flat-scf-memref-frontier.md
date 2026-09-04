# Exact TinyStories Flat-SCF Memref Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine how far the existing static-memref-view legalization moves the authenticated TinyStories-1M flat-SCF frontier, while first making evidence-only edits independent of the six-hour SCF compiler derivation.

**Architecture:** Split the derivation-visible pipeline script source from capture/verifier-only scripts, and close the carried compiler-failure predicate-authentication gap. Freeze the four real memref blocker classes from the live flat-SCF artifact, then run the already-existing `llm2fpga-lower-static-memref-views-for-calyx` pass at that boundary. Register only a proven zero-blocker normalized artifact; otherwise stop with a deterministic residual-frontier receipt before changing compiler behavior.

**Tech Stack:** Nix flakes/filesets, Python `unittest`, MLIR pass plugins, CIRCT/MLIR, canonical JSON/SHA-256 evidence.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve the exact model, adapter, package, Task 1--3 identities, authenticated Torch/Linalg/SCF artifacts, and immutable c22 flat-SCF frontier evidence.
- Do not modify Torch-MLIR shift semantics, quantization, fixed-point arithmetic, model code, DDR3, PCIe, board integration, Calyx, or RTL in this plan.
- Capture/verifier/report-only source edits must not change the Nix derivation paths for authenticated Torch, Linalg, SCF, or flat-SCF compiler outputs.
- Compiler-failure evidence is acceptable only when its predicate script is independently reconstructed from the bound derivation command/input/exit/diagnostic/operation/types and replayed on both full and verified-minimal inputs.
- The four registered memref blocker classes are `memref.reinterpret_cast`, `memref.collapse_shape`, `memref.copy`, and `memref.expand_shape`; every count and representative case must be recomputed from the live registered flat-SCF output rather than copied from prose.
- Evaluate the existing `llm2fpga-lower-static-memref-views-for-calyx` pass before extending compiler behavior.
- Do not invoke Calyx unless a normalized flat-SCF artifact has an `ok` manifest and zero registered blockers.
- Stop after the first invalid stage and preserve two byte-identical, self-hashed, live-verified bundles.
- Use test-first development and commit every verified task.

---

### Task 1: Decouple Evidence Scripts and Authenticate Compiler-Failure Predicates

**Files:**
- Modify: `flake.nix`
- Create: `tests/test_exact_pipeline_source_closure.py`
- Modify: `scripts/pipeline/classify_tinystories_1m_exact_frontier.py`
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py`
- Modify: `tests/test_tinystories_1m_exact_frontier_determinism.py`
- Modify: `docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md`

**Interfaces:**
- Consumes: all `${pipelineScripts}/...` runtime references in `flake.nix` and `nix/pipeline.nix`, plus the compiler-failure receipt union.
- Produces: `pipelineRuntimeScripts`, a filtered Nix source containing exactly compiler/runtime files named by those references and excluding classifier/verifier/report scripts.
- Produces: independent verifier reconstruction of canonical `interestingness-test.sh` bytes from bound compiler evidence.

- [ ] **Step 1: Write source-closure and predicate attack tests red**

Require the runtime source allowlist to equal the sorted set of basenames referenced as `${pipelineScripts}/...` in `flake.nix` and `nix/pipeline.nix`; reject missing runtime files and accidental inclusion of `classify_*`, `verify_*`, docs, tests, or artifacts. Add an evaluation test proving a capture/verifier-only content mutation changes neither the filtered runtime-source NAR hash nor the exact alias Torch/Linalg/SCF/flat-SCF derivation paths. Add the accepted self-consistent fake-predicate/fake-log compiler-failure bundle mutation and require public-verifier rejection.

- [ ] **Step 2: Run red tests**

```bash
nix develop -c python -m unittest tests/test_exact_pipeline_source_closure.py -v
nix develop -c python -m unittest tests.test_tinystories_1m_exact_frontier_determinism -v
```

Expected: the source-closure test fails because the whole pipeline directory is derivation-visible; the fake predicate remains accepted.

- [ ] **Step 3: Filter the derivation-visible runtime source**

Define one sorted basename allowlist in `flake.nix` from the current `${pipelineScripts}/...` consumers and construct `pipelineRuntimeScripts` with `builtins.path { path = ./scripts/pipeline; filter = ...; }`. Pass that filtered path only to derivations that execute runtime scripts. Keep classifier, capture, verifier, tests, docs, and evidence outside this source. Fail evaluation when a referenced runtime basename is absent. Do not change any runtime file bytes or command line.

- [ ] **Step 4: Reconstruct compiler predicates independently**

Keep classifier predicate generation deterministic. In the verifier, render the expected script independently from the receipt-bound build command, upstream input placeholder, expected nonzero exit, normalized diagnostic, and optional operation/types. Require byte equality with bundled/public scripts. Replay the exact predicate on full input and, when minimization is `verified`, on `minimal-reproducer.mlir`; compare both exact logs. Reject scripts that always succeed, omit the bound compiler, alter input substitution, weaken diagnostic matching, or accept an environment failure.

- [ ] **Step 5: Verify derivation stability and commit**

```bash
nix develop -c python -m unittest tests/test_exact_pipeline_source_closure.py tests/test_tinystories_1m_exact_frontier_determinism.py -v
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add flake.nix tests/test_exact_pipeline_source_closure.py scripts/pipeline/classify_tinystories_1m_exact_frontier.py scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py tests/test_tinystories_1m_exact_frontier_determinism.py docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md
git commit -m "fix: decouple exact compiler evidence tooling"
```

Expected: cached c22 evidence verifies unchanged; a verifier-only mutation leaves the four exact alias derivation paths identical.

### Task 2: Freeze the Live Flat-SCF Memref Blocker Contract

**Files:**
- Create: `scripts/pipeline/extract_tinystories_1m_exact_memref_blockers.py`
- Create: `scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py`
- Create: `tests/test_tinystories_1m_exact_memref_blockers.py`
- Create: `artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json`
- Create: `reproducers/tinystories-1m-exact-flat-scf-memref/`
- Create: `docs/results/2026-08-31-tinystories-1m-exact-memref-blockers.md`

**Interfaces:**
- Consumes: live registered alias flat-SCF `flat.scf.mlir`, `blockers.json`, manifest, and c22 receipt.
- Produces: a canonical self-hashed contract with exact per-operation counts, locations, type/shape/stride/offset signatures, and at least one exact-interestingness-checked representative MLIR module per blocker class.

- [ ] **Step 1: Write parser/identity tests red**

Require exactly the four registered memref operation classes; independently parse MLIR operations and compare their locations/counts to the live blocker JSON. Require deterministic representative selection by the lexicographically smallest canonical `(operation, type signature, source location)` tuple, while also retaining every unique canonical signature and its multiplicity. Reject copied/stale counts, altered live payloads, unknown classes, malformed affine/static metadata, or representatives that do not parse with the pinned MLIR tool.

- [ ] **Step 2: Run red tests**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_blockers.py -v
```

Expected: fail because extractor, contract, verifier, and representatives are absent.

- [ ] **Step 3: Extract live semantics and representatives**

Resolve the exact registered flat-SCF output through Nix and bind its derivation, manifest, MLIR, blockers, tool, c22 receipt, and Task 1--3 identities. Parse balanced MLIR operations without regex-truncating multiline syntax. For each class, preserve operand/result memref types, ranks, shapes, layouts, offsets, strides, reassociation indices, dynamic/static operands, and location. Emit standalone parseable representatives with unchanged operation/types and an interestingness test requiring that exact class/signature.

- [ ] **Step 4: Independently verify and commit**

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py
nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_blockers.py -v
git add scripts/pipeline/extract_tinystories_1m_exact_memref_blockers.py scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py tests/test_tinystories_1m_exact_memref_blockers.py artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json reproducers/tinystories-1m-exact-flat-scf-memref docs/results/2026-08-31-tinystories-1m-exact-memref-blockers.md
git commit -m "test: freeze exact flat scf memref blockers"
```

### Task 3: Evaluate the Existing Static-Memref-View Pass

**Files:**
- Create: `scripts/pipeline/evaluate_tinystories_1m_exact_memref_pass.py`
- Create: `scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py`
- Create: `tests/test_tinystories_1m_exact_memref_pass.py`
- Create: `artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json`
- Create: `docs/results/2026-08-31-tinystories-1m-exact-memref-pass.md`

**Interfaces:**
- Consumes: Task 2 contract, live flat-SCF artifact, pinned MLIR tool, and existing pass plugin.
- Produces: before/after operation census and blocker report for pass pipeline `builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)` on every representative and the complete artifact.

- [ ] **Step 1: Write evaluation tests red**

Require unchanged input hashes, pinned plugin/tool hashes, exact pass pipeline, parseable output, per-signature before/after mappings, no new unknown blocker classes, and semantic shape/layout invariants. The evaluator must classify each input signature as `eliminated`, `preserved`, `rewritten_equivalent`, or `new_invalid`; it may not call any later Calyx stage.

- [ ] **Step 2: Run representative evaluation red, then implement**

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_pass.py -v
```

Run the existing pass first on every Task 2 representative, then on the complete live artifact. Re-run the same blocker census on output. Preserve exact stdout/stderr/output bytes and elapsed time. Do not modify the pass in this task.

- [ ] **Step 3: Apply the decision gate**

If the complete output parses and all four registered blocker counts become zero without new invalid classes, record `decision: register_existing_pass` and identify the exact normalized artifact/hash for the next plan. Otherwise record `decision: compiler_pass_extension`, identify the earliest remaining canonical signature, and create a minimal exact reproducer for only that signature. Neither decision authorizes implementation here.

- [ ] **Step 4: Verify and commit**

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py
nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_pass.py -v
scripts/agent/pre_final_check.sh
git add scripts/pipeline/evaluate_tinystories_1m_exact_memref_pass.py scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py tests/test_tinystories_1m_exact_memref_pass.py artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json docs/results/2026-08-31-tinystories-1m-exact-memref-pass.md reproducers/tinystories-1m-exact-flat-scf-memref
git commit -m "test: evaluate existing exact memref legalization"
```

## Follow-Up Rule

- If Task 3 selects `register_existing_pass`, write a bounded registration/capture plan requiring an `ok` zero-blocker normalized flat-SCF manifest before Calyx.
- If Task 3 selects `compiler_pass_extension`, write a bounded plan for the single earliest remaining canonical signature and its before/after semantic regression.
- Float-math observations remain outside this plan and become eligible only after the registered memref blocker count is zero.
