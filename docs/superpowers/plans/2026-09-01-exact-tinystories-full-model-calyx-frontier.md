# Exact TinyStories Full-Model Calyx Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the authenticated TinyStories-1M `pre-calyx.mlir` through pinned full-model SCF-to-Calyx exactly once, then produce independently replayable, hash-bound evidence of either a valid Calyx artifact or the earliest backend diagnostic and a verified minimal reproducer.

**Architecture:** Add a dedicated exact-model Calyx derivation that consumes the reviewed normalized package rather than the obsolete generic pipeline route. A small strict runner treats nonzero exit, terminal diagnostics, empty output, malformed Calyx, or partial output as failure; an independent verifier checks all authority bindings and replays the backend command. This plan diagnoses and records the boundary only; any compiler fix requires a successor plan tied to the observed evidence.

**Tech Stack:** Nix flakes, CIRCT `circt-opt`, MLIR/Calyx, Bash, Python 3.11 `unittest`, SHA-256, `mlir-reduce` when practical.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Consume only `.#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf` and its authenticated `pre-calyx.mlir`; do not re-normalize or change the model, quantization, tokenizer, or preparation pipeline.
- Require predecessor manifest `calyx_authorized: true`, prepared SHA-256 `54a7df3fec336c5418d3562441a3f9affe45702eb107b89092bc2f7b53afca31`, and receipt self-hash `451628dba61ea805b09007e89b2135d00dcd93cf225ed4d6d9625a05a598de30`.
- Invoke pinned CIRCT only as `circt-opt INPUT --lower-scf-to-calyx=top-level-function=main -o OUTPUT`.
- A zero exit is insufficient: reject terminal diagnostics, empty output, parse failure, missing `calyx.component @main`, and any discarded partial artifact.
- Record complete command, input/output/log byte counts and hashes, CIRCT executable hash/version, derivation identity, and manifest self-hash.
- Do not modify compiler passes, Calyx lowering, the prepared artifact, or SystemVerilog stages in this plan.
- Use Nix-provided Python and tools, test first, and commit every verified task.

---

### Task 1: Implement a Strict Hash-Bound Exact Calyx Stage

**Files:**
- Create: `scripts/pipeline/run_exact_tinystories_calyx.py`
- Create: `nix/exact-tinystories-calyx.nix`
- Create: `tests/test_exact_tinystories_calyx_stage.py`
- Modify: `flake.nix`

**Interfaces:**
- Consumes: predecessor package path, expected prepared and receipt hashes, pinned `circt-opt`, and output directory.
- Produces: `run_calyx(input_path: Path, output_dir: Path, circt_opt: Path) -> dict[str, object]` and package `tiny-stories-1m-kev-gpt-exact-calyx-frontier` containing `manifest.json`, `lower-scf-to-calyx.log`, and either valid `model.calyx.mlir` or a preserved `partial.calyx.mlir` marked invalid.

- [ ] **Step 1: Write fail-closed RED tests**

Use fake backend executables to cover: zero exit plus `Unhandled operation`; nonzero exit; zero exit with empty output; zero exit with malformed output; valid output containing `calyx.component @main`; predecessor with false authorization; and predecessor hash mismatch. Assert that only the valid case has `status == "ok"` and `artifact_accepted == true`.

```python
self.assertEqual(result["stage"], "calyx")
self.assertEqual(result["status"], "failed")
self.assertFalse(result["artifact_accepted"])
self.assertEqual(result["first_diagnostic"], "Unhandled operation during BuildOpGroups()")
```

- [ ] **Step 2: Run RED tests**

```bash
nix develop -c python -m unittest tests/test_exact_tinystories_calyx_stage.py -v
```

Expected: failure because the runner and exact package do not exist.

- [ ] **Step 3: Implement the strict runner**

Run the exact command without a shell, combine stdout/stderr into the canonical log, and classify terminal lines using the existing case-insensitive patterns `error:`, `failed to legalize operation`, `unhandled operation`, and `LLVM ERROR`. Preserve nonempty rejected output as `partial.calyx.mlir`, never as the accepted artifact. Parse a candidate with `circt-opt candidate -o /dev/null` and require `calyx.component @main`. Serialize canonical JSON with a self-hash computed over the object without `sha256`.

- [ ] **Step 4: Register the exact Nix derivation**

`nix/exact-tinystories-calyx.nix` must validate the predecessor manifest and the two fixed hashes before calling the runner with `${circt}/bin/circt-opt`. Export only:

```nix
"tiny-stories-1m-kev-gpt-exact-calyx-frontier" = exactTinyStoriesCalyx;
```

Do not add it to the old `pipelineStagePackagesNoHandshake` graph.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python -m unittest tests/test_exact_tinystories_calyx_stage.py -v
nix eval .#packages.x86_64-linux.tiny-stories-1m-kev-gpt-exact-calyx-frontier.name
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add scripts/pipeline/run_exact_tinystories_calyx.py \
  nix/exact-tinystories-calyx.nix tests/test_exact_tinystories_calyx_stage.py flake.nix
git commit -m "feat: register exact TinyStories Calyx frontier"
```

### Task 2: Capture, Replay, and Reduce the Full-Model Result

**Files:**
- Create: `scripts/pipeline/verify_exact_tinystories_calyx_frontier.py`
- Create: `tests/test_exact_tinystories_calyx_frontier.py`
- Create: `artifacts/comparison/tinystories-1m-exact-calyx-frontier.json`
- Create: `docs/results/2026-09-01-exact-tinystories-full-model-calyx-frontier.md`
- Create when failure is reducible: `reproducers/tinystories-1m-exact-calyx-frontier/interesting.sh`
- Create when failure is reducible: `reproducers/tinystories-1m-exact-calyx-frontier/minimal.mlir`

**Interfaces:**
- Consumes: Task 1 package manifest, log, candidate/partial artifact, predecessor manifest, and pinned tool identities.
- Produces: `verify_bundle(bundle: Path, predecessor: Path) -> dict[str, object]`, a canonical frontier receipt, and either a verified valid Calyx binding or a verified first diagnostic/minimal reproducer binding.

- [ ] **Step 1: Write mutation and replay RED tests**

Require rejection after mutating input hash, predecessor receipt hash, command, tool hash, log, candidate artifact, diagnostic, result status, or receipt self-hash. Require a coherent forged manifest to fail because independent replay disagrees.

```python
with self.assertRaisesRegex(ValueError, "replay result differs"):
    verify_bundle(forged_bundle, predecessor)
```

- [ ] **Step 2: Run RED tests**

```bash
nix develop -c python -m unittest tests/test_exact_tinystories_calyx_frontier.py -v
```

Expected: failure because the independent verifier is absent.

- [ ] **Step 3: Build and independently replay the exact full model**

```bash
nix build .#tiny-stories-1m-kev-gpt-exact-calyx-frontier -L
nix develop -c python scripts/pipeline/verify_exact_tinystories_calyx_frontier.py \
  --bundle result \
  --predecessor /nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf \
  --output artifacts/comparison/tinystories-1m-exact-calyx-frontier.json
```

The verifier must independently execute the exact command against the authenticated predecessor input in a temporary directory and compare status, first diagnostic, log classification, and candidate hash. Environment failure is not a compiler frontier.

- [ ] **Step 4: Minimize only an observed compiler failure**

If status is `failed` with a stable compiler diagnostic, create `interesting.sh` that returns success only when the pinned command reproduces the same normalized first diagnostic. Run:

```bash
nix develop -c mlir-reduce \
  --test=reproducers/tinystories-1m-exact-calyx-frontier/interesting.sh \
  /nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf/pre-calyx.mlir \
  -o reproducers/tinystories-1m-exact-calyx-frontier/minimal.mlir
```

Re-run interestingness on `minimal.mlir` and bind both hashes. If reduction cannot finish within the executor's bounded run, record `minimization.status = "not_practical"`, the exact command, elapsed time, reducer log hash, and full-input hash; do not invent a smaller fixture.

- [ ] **Step 5: Record exactly one result**

For success, record `status=complete`, the parsed nonempty Calyx artifact hash, and no diagnostic. For failure, record `status=compiler_frontier`, `frontier=calyx_frontier`, the normalized earliest diagnostic, complete full-input binding, and verified minimization result. Do not propose or implement a fix in this document.

- [ ] **Step 6: Verify and commit**

```bash
nix develop -c python -m unittest \
  tests/test_exact_tinystories_calyx_stage.py \
  tests/test_exact_tinystories_calyx_frontier.py -v
nix develop -c python scripts/pipeline/verify_exact_tinystories_calyx_frontier.py \
  --bundle result \
  --predecessor /nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf \
  --output /tmp/tinystories-calyx-replay.json
cmp artifacts/comparison/tinystories-1m-exact-calyx-frontier.json \
  /tmp/tinystories-calyx-replay.json
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add scripts/pipeline/verify_exact_tinystories_calyx_frontier.py \
  tests/test_exact_tinystories_calyx_frontier.py \
  artifacts/comparison/tinystories-1m-exact-calyx-frontier.json \
  docs/results/2026-09-01-exact-tinystories-full-model-calyx-frontier.md \
  reproducers/tinystories-1m-exact-calyx-frontier
git commit -m "test: record exact TinyStories Calyx frontier"
```

## Follow-Up Rule

- A valid Calyx artifact authorizes a separate Calyx-to-SystemVerilog plan.
- A compiler frontier authorizes only one evidence-backed plan for its first reproduced diagnostic or causal structure.
- Neither result authorizes synthesis, board integration, Representative Core substitution, PCIe, or DDR3 work.
