# Exact TinyStories SCF Registration Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register the repository's existing direct Linalg-to-SCF no-handshake route for the frozen exact TinyStories model and capture the first validly evidenced frontier after that registration without changing compiler behavior.

**Architecture:** Add one public pipeline alias that selects the already-defined `pipelineStagePackagesNoHandshake` route for `tiny-stories-1m-kev-gpt-exact`; do not add a pass, rewrite, backend override, or new lowering. Prove the alias reuses the authenticated Torch/Linalg inputs, then make the exact frontier runner select that alias from `torch` through `calyx-native-sv`, stopping at the first invalid artifact and preserving two independently verified bundles.

**Tech Stack:** Nix flakes, Python 3 `unittest`, MLIR/Torch-MLIR/CIRCT pipeline derivations, JSON SHA-256 receipts.

**Spec:** `docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md`

## Global Constraints

- Preserve the model key `tiny-stories-1m-kev-gpt-exact` and every frozen adapter, package, Task 1 audit, Task 2 model, Task 3 generation, semantic fixture, and registered Torch artifact identity.
- Select only the existing `pipelineStagePackagesNoHandshake` direct Linalg route; do not modify `nix/pipeline.nix`, a compiler patch, a lowering pass, the adapter, the model package, or backend semantics.
- Use the alias `tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake` and the stage order `pytorch-exported`, `torch`, `linalg`, `scf`, `flat-scf`, `calyx`, `calyx-native-sv`.
- Run the live compiler-backed semantic verifier before any registered build.
- Stop immediately after the first invalid stage. A zero-exit control manifest is rejected when its exact stage/status/reason contract does not establish a usable artifact; a nonzero compiler exit is a validly captured frontier even when no manifest was produced.
- Preserve full failing input, exact logs, exact derivation bytes/JSON/build commands, operation/types when present, exact interestingness and a minimal reproducer when practical, classifier/verifier identities, and two byte-identical self-hashed bundles. Never fabricate a manifest for the nonzero compiler-failure branch.
- If `calyx-native-sv` succeeds, validate its emitted SystemVerilog with the registered syntax/synthesis route and hash it; do not claim board inference.
- This plan ends at the newly captured frontier or synthesizable SystemVerilog evidence. Any compiler fix requires another bounded plan.

---

### Task 1: Register the existing exact no-handshake route

**Files:**
- Modify: `flake.nix` in `pipelineAliasSpecs`
- Modify: `tests/test_tinystories_1m_exact_pipeline_registration.py`

**Interfaces:**
- Consumes: `pipelineStagePackagesNoHandshake`, `noHandshakeLinalgStages`, and model key `tiny-stories-1m-kev-gpt-exact`.
- Produces: public attributes named `tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-${stage}` for every stage in `noHandshakeLinalgStages`.

- [ ] **Step 1: Write the failing alias-registration test**

Add this test to `TinyStories1mExactPipelineRegistrationTest`:

```python
def test_exact_model_registers_existing_linalg_no_handshake_route(self) -> None:
    alias = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake"
    flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
    self.assertIn(f'alias = "{alias}";', flake)
    self.assertIn('model = "tiny-stories-1m-kev-gpt-exact";', flake)
    for stage in ("torch", "linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"):
        result = subprocess.run(
            ["nix", "eval", "--raw", f".#packages.x86_64-linux.{alias}-{stage}"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("/nix/store/"))
```

- [ ] **Step 2: Run the registration test red**

Run:

```bash
nix develop -c python -m unittest \
  tests.test_tinystories_1m_exact_pipeline_registration.TinyStories1mExactPipelineRegistrationTest.test_exact_model_registers_existing_linalg_no_handshake_route -v
```

Expected: fail because no exact-model Linalg/no-handshake alias exists.

- [ ] **Step 3: Add the exact alias without changing pipeline implementation**

Append this object to `pipelineAliasSpecs` in `flake.nix`:

```nix
{
  alias = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake";
  model = "tiny-stories-1m-kev-gpt-exact";
  frontend = "linalg";
  backend = "calyx-native-sv";
  packages = pipelineStagePackagesNoHandshake;
  stages = noHandshakeLinalgStages;
}
```

- [ ] **Step 4: Prove the alias reuses the authenticated Torch and Linalg stages**

Add `test_exact_no_handshake_alias_reuses_authenticated_prefix` to `TinyStories1mExactPipelineRegistrationTest`. For each stage in `("torch", "linalg")`, run both of these exact commands with `stage` substituted by the loop value:

```python
direct = subprocess.run(
    ["nix", "eval", "--raw", f".#packages.x86_64-linux.tiny-stories-1m-kev-gpt-exact-{stage}"],
    cwd=ROOT, text=True, capture_output=True,
)
alias = subprocess.run(
    ["nix", "eval", "--raw", f".#packages.x86_64-linux.tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-{stage}"],
    cwd=ROOT, text=True, capture_output=True,
)
self.assertEqual(direct.returncode, 0, direct.stderr)
self.assertEqual(alias.returncode, 0, alias.stderr)
self.assertEqual(alias.stdout, direct.stdout)
```

Also run `git diff --exit-code HEAD^ -- nix/pipeline.nix patches/torch-mlir` and require exit zero so this task cannot hide a compiler or lowering change.

- [ ] **Step 5: Run the complete registration suite green**

Run:

```bash
nix develop -c python -m unittest tests/test_tinystories_1m_exact_pipeline_registration.py -v
nix flake check --no-build
```

Expected: all registration tests pass and the flake evaluates without building later stages.

- [ ] **Step 6: Commit the registration decision**

```bash
git add flake.nix tests/test_tinystories_1m_exact_pipeline_registration.py
git commit -m "feat: register exact Linalg to SCF route"
```

---

### Task 2: Route the authenticated classifier through the registered alias

**Files:**
- Modify: `scripts/pipeline/classify_tinystories_1m_exact_frontier.py`
- Modify: `tests/test_tinystories_1m_exact_frontier.py`

**Interfaces:**
- Consumes: alias prefix `tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake`, Task 2 semantic verifier output, and the Task 3 SCF availability receipt.
- Produces: `_registered_attribute(model: str, stage: str) -> str`, returning the direct `${model}-pytorch-exported` attribute for export and the alias `${alias}-${stage}` for `torch` through `calyx-native-sv`.
- Produces: `_classify_registered_result(stage: str, exit_code: int, output: Path, upstream_input: Path | None, log: Path) -> RegisteredStageResult`; this function returns exactly one of the three result variants below, and `_run_registered_stage(...) -> tuple[StageRecord, dict[str, object], RegisteredStageResult]` carries it without converting compiler failures into manifest failures.

```python
@dataclass(frozen=True)
class AcceptedStageResult:
    kind: Literal["accepted"]
    artifact: Path
    output: Path

@dataclass(frozen=True)
class ControlManifestFailure:
    kind: Literal["control_manifest"]
    manifest: Path
    upstream_input: Path
    diagnostic: str

@dataclass(frozen=True)
class CompilerFailure:
    kind: Literal["compiler_failure"]
    upstream_input: Path
    log: Path
    diagnostic: str
    operation: str | None
    types: str | None

RegisteredStageResult = AcceptedStageResult | ControlManifestFailure | CompilerFailure
```

- [ ] **Step 1: Write the failing route-selection test**

```python
def test_exact_runner_selects_registered_linalg_no_handshake_alias(self) -> None:
    model = "tiny-stories-1m-kev-gpt-exact"
    self.assertEqual(
        MODULE._registered_attribute(model, "pytorch-exported"),
        "tiny-stories-1m-kev-gpt-exact-pytorch-exported",
    )
    for stage in ("torch", "linalg", "scf", "flat-scf", "calyx", "calyx-native-sv"):
        self.assertEqual(
            MODULE._registered_attribute(model, stage),
            f"tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake-{stage}",
        )
```

- [ ] **Step 2: Run the route-selection test red**

Run:

```bash
nix develop -c python -m unittest \
  tests.test_tinystories_1m_exact_frontier.AuthenticatedPipelineRunnerTest.test_exact_runner_selects_registered_linalg_no_handshake_alias -v
```

Expected: fail because `_registered_attribute` does not exist and the runner still selects baseline `${model}-${stage}` attributes.

- [ ] **Step 3: Implement the fixed route mapping**

```python
_EXACT_LINALG_ALIAS = "tiny-stories-1m-kev-gpt-exact-via-linalg-no-handshake"

def _registered_attribute(model: str, stage: str) -> str:
    if model != "tiny-stories-1m-kev-gpt-exact":
        raise ValueError(f"unsupported exact model: {model}")
    if stage == "pytorch-exported":
        return f"{model}-pytorch-exported"
    if stage not in _FRONTIERS:
        raise ValueError(f"unregistered exact stage: {stage}")
    return f"{_EXACT_LINALG_ALIAS}-{stage}"
```

Use this function in `_run_registered_stage` and in independent derivation verification. Record the alias, frontend `linalg`, backend `calyx-native-sv`, and exact attribute in every stage execution record.

- [ ] **Step 4: Write red tests for both invalid-result branches**

Add these tests to `AuthenticatedPipelineRunnerTest` using temporary real files and the classifier result helper:

```python
def setUp(self) -> None:
    self.temporary = tempfile.TemporaryDirectory(prefix="exact-scf-result-union-")
    self.addCleanup(self.temporary.cleanup)
    root = Path(self.temporary.name)
    self.linalg_input = root / "input.linalg.mlir"
    self.linalg_input.write_text("module {}\n", encoding="utf-8")
    self.unavailable_scf_output = root / "scf-output"
    self.unavailable_scf_output.mkdir()
    (self.unavailable_scf_output / "manifest.json").write_text(
        '{"reason":"no direct SCF route","stage":"scf","status":"unavailable"}\n',
        encoding="utf-8",
    )
    self.scf_log = root / "scf-control.log"
    self.scf_log.write_text("registered control output\n", encoding="utf-8")
    self.nonzero_scf_log = root / "scf-compiler.log"
    self.nonzero_scf_log.write_text(
        "error: failed to legalize operation 'scf.for' : (index) -> ()\n",
        encoding="utf-8",
    )
    self.no_output_path = root / "no-output"

def test_zero_exit_unavailable_manifest_returns_control_manifest_failure(self) -> None:
    result = MODULE._classify_registered_result(
        stage="scf", exit_code=0, output=self.unavailable_scf_output,
        upstream_input=self.linalg_input, log=self.scf_log,
    )
    self.assertIsInstance(result, MODULE.ControlManifestFailure)
    self.assertEqual(result.kind, "control_manifest")
    self.assertEqual(result.manifest, self.unavailable_scf_output / "manifest.json")
    self.assertEqual(result.upstream_input, self.linalg_input)

def test_nonzero_scf_failure_returns_compiler_failure_without_manifest(self) -> None:
    result = MODULE._classify_registered_result(
        stage="scf", exit_code=1, output=self.no_output_path,
        upstream_input=self.linalg_input, log=self.nonzero_scf_log,
    )
    self.assertIsInstance(result, MODULE.CompilerFailure)
    self.assertEqual(result.kind, "compiler_failure")
    self.assertEqual(result.upstream_input, self.linalg_input)
    self.assertEqual(result.log, self.nonzero_scf_log)
    self.assertFalse(hasattr(result, "manifest"))

def test_nonzero_scf_failure_preserves_full_diagnostic_and_optional_operation_types(self) -> None:
    identified = MODULE._classify_registered_result(
        stage="scf", exit_code=1, output=self.no_output_path,
        upstream_input=self.linalg_input, log=self.nonzero_scf_log,
    )
    self.assertEqual(identified.operation, "scf.for")
    self.assertEqual(identified.types, "(index) -> ()")
    anonymous_log = Path(self.temporary.name) / "anonymous.log"
    anonymous_log.write_text("error: compiler terminated\n", encoding="utf-8")
    anonymous = MODULE._classify_registered_result(
        stage="scf", exit_code=2, output=self.no_output_path,
        upstream_input=self.linalg_input, log=anonymous_log,
    )
    self.assertIsNone(anonymous.operation)
    self.assertIsNone(anonymous.types)
```

Run all three named tests red before implementation.

- [ ] **Step 5: Implement the result union and fail closed**

Add the dataclasses and `RegisteredStageResult` union exactly as declared above. `_classify_registered_result` must apply these rules in order:

1. `exit_code != 0`: require the preserved log to contain a terminal compiler diagnostic; return `CompilerFailure` with the authenticated upstream Linalg artifact as `upstream_input`, parse operation/types only when present, and do not search for or synthesize `manifest.json`.
2. `exit_code == 0` and a manifest exists: parse it. Return `AcceptedStageResult` only when its exact stage/status/reason contract establishes `status == "ok"` and a nonempty primary artifact. Otherwise return `ControlManifestFailure`, retaining the exact manifest and normalized classifier diagnostic.
3. `exit_code == 0` without a valid manifest where that stage requires one, or without a nonempty primary artifact: raise `RuntimeError`; this is invalid evidence, not a compiler frontier.

Record both invalid variants as `status == "compiler_failure"`, `artifact_accepted == false`, and stop the registered sequence. A `ControlManifestFailure` has exit zero and binds the manifest as its reproducer. A `CompilerFailure` has the actual nonzero exit, binds the upstream Linalg input separately, and has no manifest field.

- [ ] **Step 6: Add a fail-closed identity test**

Build only the alias `torch` and `linalg` attributes and assert their artifact SHA-256 values equal the current authenticated direct-stage hashes before permitting SCF. Mutate either trusted hash in the test fixture and require classifier rejection before `_run_registered_pipeline` can call `scf`.

- [ ] **Step 7: Run classifier and semantic suites green**

```bash
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py \
  --probe-report artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_frontier.py \
  tests/test_tinystories_1m_exact_frontier_semantics.py -v
```

Expected: semantic replay accepts current bytes and all route/stop tests pass.

- [ ] **Step 8: Commit the routed classifier**

```bash
git add scripts/pipeline/classify_tinystories_1m_exact_frontier.py tests/test_tinystories_1m_exact_frontier.py
git commit -m "test: route exact classifier through registered SCF"
```

---

### Task 3: Capture the next first invalid stage

**Files:**
- Modify: `artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json`
- Modify: `docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md`
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py`
- Modify: `tests/test_tinystories_1m_exact_frontier_determinism.py`
- Create: the `reproducers/` child named by the receipt's validated `first_invalid_stage`
- Create: the `artifacts/comparison/tinystories-1m-exact-frontier-determinism-` child suffixed by that same validated stage

**Interfaces:**
- Consumes: the committed alias/runner code, live semantic proof, and exact registered stage attributes from Tasks 1--2.
- Produces: two byte-identical self-hashed bundles and one successor receipt for exactly the earliest invalid registered alias stage, or validated synthesizable SystemVerilog evidence.
- Produces: a `frontier_evidence` receipt union. Its discriminator is `kind == "control_manifest"` for a zero-exit unavailable/rejected control manifest or `kind == "compiler_failure"` for a nonzero compiler failure without a manifest.

- [ ] **Step 1: Commit all capture code before evidence generation**

Run `scripts/agent/pre_final_check.sh` and require a clean worktree. Record `git rev-parse HEAD`; this exact commit is the receipt `source_commit`. Compute and later bind SHA-256 for the classifier, semantic verifier, and determinism verifier from that commit's bytes.

- [ ] **Step 2: Run the first classifier capture**

```bash
python3 scripts/pipeline/classify_tinystories_1m_exact_frontier.py \
  --model tiny-stories-1m-kev-gpt-exact \
  --output /tmp/exact-scf-route-run-1/receipt.json \
  --evidence-dir /tmp/exact-scf-route-run-1
```

Expected: semantic verification runs first; stages run in registered order; execution stops immediately at the first invalid alias stage.

- [ ] **Step 3: Run the independent second capture**

```bash
python3 scripts/pipeline/classify_tinystories_1m_exact_frontier.py \
  --model tiny-stories-1m-kev-gpt-exact \
  --output /tmp/exact-scf-route-run-2/receipt.json \
  --evidence-dir /tmp/exact-scf-route-run-2
```

- [ ] **Step 4: Require byte identity before promotion**

Use `cmp` for `receipt.json`, every executed-stage log, the full failing-input archive, and every captured derivation `.drv`/canonical JSON file. For `control_manifest`, also compare `minimal-reproducer.json`. For `compiler_failure`, compare `interestingness-test.sh`, `interesting-full.log`, `reduction.log`, and—when reduction is verified—`minimal-reproducer.mlir` plus `interesting-reproducer.log`. Any mismatch aborts promotion and requires a classifier normalization test/fix in a separate code commit before rerunning both captures.

The bundle verifier, not the receipt manifest, derives the exact regular-file set from the fixed stage order, the executed prefix, `frontier_evidence.kind`, and `frontier_evidence.minimization.status`. No other file, hidden entry, symlink, directory, or device is permitted.

- [ ] **Step 5: Validate the observed frontier independently**

Run:

Derive and validate the stage name, then invoke the verifier with the exact resulting path:

```bash
first_invalid_stage="$(python3 -c 'import json; print(json.load(open("artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json"))["pipeline_execution"]["first_invalid_stage"])')"
case "$first_invalid_stage" in
  scf|flat-scf|calyx|calyx-native-sv) ;;
  *) exit 1 ;;
esac
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py \
  --bundle-dir "artifacts/comparison/tinystories-1m-exact-frontier-determinism-${first_invalid_stage}"
```

The classifier and verifier must implement these deterministic receipt rules:

- `frontier_evidence.kind == "control_manifest"` requires stage exit zero, `artifact_accepted == false`, the exact rejected/unavailable manifest bytes, exact stage/status/reason validation, `operation == null`, `types == null`, and `minimization == {"status": "not_applicable", "reason": "control_manifest_is_minimal"}`. `minimal-reproducer.json` is the copied manifest and is the only permitted minimal-reproducer file.
- `frontier_evidence.kind == "compiler_failure"` requires a nonzero stage exit, `artifact_accepted == false`, `manifest == null`, the full diagnostic/log, the preserved upstream Linalg input, and exact tool/derivation/build-command bindings. `operation` and `types` are exact strings when the diagnostic or failing MLIR identifies them and literal `null` otherwise. No `manifest.json` or `minimal-reproducer.json` may exist in this branch.
- For a compiler failure, generate `interestingness-test.sh` from the captured derivation build command: it accepts one candidate path, substitutes that path for the bound Linalg input, writes output under a temporary directory, and succeeds only when the compiler returns the same nonzero exit and normalized terminal diagnostic, plus the same operation/types when non-null. Bind the script bytes/hash and prove the full Linalg input with `interesting-full.log`.
- If the full input passes interestingness and a bound `mlir-reduce` is available, decompress the bound `full-input.gz` to the noncanonical working file `full-input.mlir`, run `mlir-reduce --test=./interestingness-test.sh full-input.mlir -o minimal-reproducer.mlir`, preserve `reduction.log`, rerun the interestingness script on the result into `interesting-reproducer.log`, and require `minimization.status == "verified"` with exact minimal bytes/hash. Otherwise preserve the attempted `reduction.log` and use `minimization.status == "not_practical"` with exactly one reason from `mlir_reduce_unavailable`, `full_input_not_interesting`, or `reduction_failed`; in that status no minimal-reproducer file or binding is permitted.

The verifier must independently replay the semantic gate; recompute frozen Task 1--3 and predecessor identities; resolve every registered alias derivation; compare exact build commands, `.drv` bytes, canonical derivation JSON, outputs, logs, exits, status, and diagnostics; decompress and hash the full failing input; dispatch on the `frontier_evidence` union; validate the exact branch file set above; and reject recomputed-self-hash mutations that cross or mix branches.

Add public adversarial tests named `test_control_manifest_branch_rejects_nonzero_exit_or_missing_manifest`, `test_compiler_failure_branch_rejects_zero_exit_or_any_manifest`, `test_compiler_failure_branch_preserves_linalg_input_log_tool_and_command`, `test_compiler_failure_branch_rejects_unbound_operation_or_types`, and `test_branch_specific_directory_sets_reject_cross_branch_files`. Each test copies a real bundle fixture, makes the named mutation, recomputes the receipt self-hash, and still requires verifier rejection.

- [ ] **Step 6: Validate SystemVerilog only if the final stage succeeds**

If and only if `calyx-native-sv` is valid, build the registered alias `il` and `yosys-stat` attributes, require both manifests to report `status: ok`, and record the emitted `sv/main.sv` SHA-256 plus syntax/synthesis logs. Record `board_inference: false` unconditionally.

- [ ] **Step 7: Run final regression and provenance gates**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_pipeline_registration.py \
  tests/test_tinystories_1m_exact_frontier_semantics.py \
  tests/test_tinystories_1m_exact_frontier.py \
  tests/test_tinystories_1m_exact_frontier_determinism.py -v
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
git diff --check
```

- [ ] **Step 8: Commit only the verified successor evidence**

```bash
git add artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json \
  "artifacts/comparison/tinystories-1m-exact-frontier-determinism-${first_invalid_stage}" \
  docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md \
  reproducers tests/test_tinystories_1m_exact_frontier_determinism.py \
  scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
git commit -m "test: capture registered exact SCF successor frontier"
```

## Self-Review

- The plan selects exactly one route: the existing direct Linalg/no-handshake registration.
- No task changes compiler behavior, adapter/model semantics, or frozen Task 1--3 identities.
- Every implementation change begins with a named failing test and includes its exact red/green command.
- The classifier cannot run SCF before proving alias Torch/Linalg identity and cannot run a stage after the first invalid artifact.
- The classifier and verifier cover both legal first-invalid outcomes: a zero-exit control-manifest rejection and a nonzero compiler failure with no fabricated manifest.
- Evidence generation occurs only from a committed code state, avoiding self-referential commit claims.
- The plan contains no `TBD`, `TODO`, deferred error handling, or unnamed tests.
