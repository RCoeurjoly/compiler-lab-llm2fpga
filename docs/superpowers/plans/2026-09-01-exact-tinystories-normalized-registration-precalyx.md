# Exact TinyStories Normalized Registration and Pre-Calyx Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register the exact zero-memref-blocker TinyStories-1M normalized flat-SCF artifact reproducibly, run the existing pre-Calyx preparation pipeline, and report the first complete legality frontier without invoking Calyx.

**Architecture:** Harden the pre-Calyx checker so it cannot falsely report clean when result-bearing custom/generic/escaped operations such as `math.floor`, `arith.negf`, or `math.absi` remain. Then add a Nix derivation that reproduces the reviewed normalized artifact from the immutable tracked c22 input and reviewed plugin, verifies its exact SHA-256, runs only the existing pre-Calyx MLIR preparation passes, and emits a hash-bound legality manifest. Calyx lowering remains gated off unless that prepared artifact is independently proven clean.

**Tech Stack:** Nix flakes, Python `unittest`, MLIR pass plugin/`mlir-opt`, canonical JSON/SHA-256 evidence.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve exact TinyStories-1M identities, immutable c22 input SHA-256 `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`, reviewed plugin SHA-256 `79c0ab56022ce6c91279bca8aefeea7251a1eb19c92675f6df7b90265fb0d738`, and normalized output SHA-256 `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`.
- The registered stage must be produced by replaying `builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)` from the immutable c22 input, not by copying an unauthenticated output.
- The pre-Calyx preparation pipeline is exactly the current pipeline sequence through `llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse`; it must not invoke `circt-opt`, Calyx, SV export, synthesis, or board tools.
- The legality checker must recognize result-bearing custom and generic operation spellings, MLIR hex escapes, and comments/trivia; unknown or malformed operation spellings fail closed.
- At minimum, prohibit `arith.uitofp`, `arith.negf`, `math.floor`, `math.absi`, and the four registered memref view/copy operations at the prepared boundary.
- Registration of raw normalized flat-SCF does not authorize Calyx. Only an exact prepared artifact with `status: ok` may enable a later Calyx plan.
- Use test-first development and commit every verified task.

---

### Task 1: Make the Pre-Calyx Legality Census Complete for the Observed Frontier

**Files:**
- Modify: `scripts/pipeline/calyx_preflight_report.py`
- Modify: `tests/test_calyx_preflight_report.py`
- Create: `docs/results/2026-09-01-tinystories-1m-precalyx-legality-contract.md`

**Interfaces:**
- Consumes: MLIR text at the prepared SCF-to-Calyx boundary.
- Produces: deterministic schema-v2 JSON containing full observed prohibited counts, canonical first locations, `status: ok|blocked`, and a self-hash.

- [ ] **Step 1: Write REDs for the false-clean operations**

Add result-bearing custom and generic tests for `math.floor`, `arith.negf`, and `math.absi`, including escaped generic names such as `"math.\66loor"`, SSA-result prefixes, comments between generic name and operands, and multiple occurrences. Add malformed escape/trivia tests that must fail closed rather than return clean. Preserve exact existing counts for `arith.uitofp` and memref blockers.

- [ ] **Step 2: Run RED**

```bash
nix develop -c python -m unittest tests/test_calyx_preflight_report.py -v
```

Expected: the current checker reports the three observed classes clean or undercounts generic/escaped forms.

- [ ] **Step 3: Implement a spelling-independent operation scanner**

Parse custom names and quoted generic names after optional SSA result lists, decode valid MLIR hex escapes, skip valid whitespace/line-comment trivia, and record exact line/column for each prohibited operation. Reject malformed quoted names/trivia with `status: blocked` and an explicit scanner diagnostic. Emit schema version 2 with exact keys:

```json
{
  "schema_version": 2,
  "status": "blocked",
  "prohibited_ops": {"math.floor": 1},
  "first_locations": {"math.floor": {"line": 1, "column": 8}},
  "scanner_diagnostics": [],
  "sha256": "..."
}
```

The self-hash is canonical JSON with `sha256` omitted. `--require-clean` exits 1 for prohibited operations or scanner diagnostics.

- [ ] **Step 4: Verify and commit**

```bash
nix develop -c python -m unittest tests/test_calyx_preflight_report.py -v
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add scripts/pipeline/calyx_preflight_report.py \
  tests/test_calyx_preflight_report.py \
  docs/results/2026-09-01-tinystories-1m-precalyx-legality-contract.md
git commit -m "fix: close pre calyx legality census"
```

### Task 2: Register Exact Normalized Flat-SCF and Run Preparation Only

**Files:**
- Modify: `flake.nix`
- Create: `nix/exact-tinystories-normalized.nix`
- Create: `tests/test_tinystories_1m_exact_normalized_registration.py`
- Create: `scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py`
- Create: `docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md`

**Interfaces:**
- Consumes: tracked immutable c22 MLIR, reviewed pass plugin, pinned `mlir-opt`, rank-one-copy zero-blocker receipt, and hardened legality checker.
- Produces: flake package `tiny-stories-1m-kev-gpt-exact-normalized-flat-scf` with `flat.scf.mlir`, `manifest.json`, `pre-calyx.mlir`, and `pre-calyx-legality.json`.

- [ ] **Step 1: Write registration and no-Calyx REDs**

Require the package alias and derivation to be absent before implementation. Require its source closure to contain only the exact c22 input, verifier/checker/runtime files actually executed, and plugin/tool derivations—not the full evidence directory. Require exact normalized SHA, zero registered counts, preparation pipeline string, prepared parse success, legality receipt self-hash, and absence of `circt-opt`, Calyx, SV, synthesis, or board commands. Add mutations for stale c22/plugin/output hash, false clean legality, altered pipeline, and evidence-only source changes affecting the derivation.

- [ ] **Step 2: Run RED**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py -v
```

Expected: package, derivation module, verifier, manifest, and legality output are absent.

- [ ] **Step 3: Add the reproducible registered derivation**

In `nix/exact-tinystories-normalized.nix`, accept explicit `pkgs`, `mlir`, `mlirPasses`, `python`, `c22Input`, `preflightScript`, and expected hashes. The derivation must:

1. verify c22 and plugin SHA-256;
2. replay the exact normalization pipeline to `$out/flat.scf.mlir`;
3. verify normalized SHA-256 `e669a263...d77` and parse it;
4. run the exact existing pre-Calyx preparation pipeline only, writing `$out/pre-calyx.mlir`;
5. parse the prepared MLIR;
6. run the hardened checker without `--require-clean` to `$out/pre-calyx-legality.json`;
7. write a canonical manifest binding commands, hashes, zero registered counts, and `calyx_authorized: false` unless legality status is `ok`.

Expose the package in `flake.nix` under the exact alias. Use a file-level filtered source for the tracked c22 input and checker so evidence/report-only mutations do not perturb the derivation.

- [ ] **Step 4: Build, independently verify, and classify**

```bash
nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L
nix develop -c python \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py -v
```

The verifier independently resolves the derivation, recomputes every file hash/schema/self-hash/count, reparses normalized/prepared MLIR, and confirms no Calyx command executed. If legality is blocked, record exact prohibited counts and earliest source location as the next compiler frontier. If clean, record only that a later Calyx plan is eligible; do not run it here.

- [ ] **Step 5: Commit**

```bash
git add flake.nix nix/exact-tinystories-normalized.nix \
  tests/test_tinystories_1m_exact_normalized_registration.py \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py \
  docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md
git commit -m "feat: register exact normalized TinyStories stage"
```

## Follow-Up Rule

- If prepared legality is blocked, the next plan targets only the earliest independently reconstructed prohibited operation and its exact type/semantic context.
- If prepared legality is clean, write a separate authenticated Calyx-lowering plan; do not conflate legality with successful Calyx or SystemVerilog generation.
- Synthesis, timing, board inference, and remaining goal gates stay pending until valid synthesizable SystemVerilog exists.
