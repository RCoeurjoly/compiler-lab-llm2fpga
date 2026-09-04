# Task 2 Report: Provenance-Bound Semantic Executor

Status: implemented and verified.

## Scope

Implemented `scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py` as a compiler-backed executor for the frozen five-case signed-si64 right-shift fixture. The executor does not calculate accepted outputs with Python shift operations and does not accept caller-supplied result JSON.

For every valid fixture element, the executor:

1. Builds an MLIR module containing the exact `torch.aten.bitwise_right_shift.Tensor_Scalar` operation over the complete fixture tensor shape and values.
2. Selects one result element in Torch IR so the complete lowered tensor computation returns an `i64` from `@main`.
3. Invokes the bound `torch-mlir-opt` with the receipt's exact frontend pipeline.
4. Requires the scalar form to disappear in favor of the registered tensor/tensor operation.
5. Invokes the bound Torch backend-to-Linalg pipeline and requires `arith.shrsi` with no remaining Torch right-shift operation.
6. Invokes the bound `mlir-opt` with the repository's exact Linalg-to-LLVM pass sequence and requires `llvm.ashr` in the emitted module.
7. Executes that compiler-emitted full tensor module with the bound `mlir-runner` JIT and parses its scalar stdout.

The output vectors are assembled only from those JIT results. The fixture's `expected` objects are used only as a final mismatch guard.

For invalid fixture cases, the executor invokes the exact frontend compiler pipeline, requires a nonzero compiler exit, requires the matching contract diagnostic, and emits no `output` field. Only these normalized diagnostics are accepted:

- `shift_contract:negative_shift`
- `shift_contract:greater_than_sixty_two`

## TDD evidence

Precheck:

- `scripts/agent/pre_final_check.sh` exited 0 on the initial clean worktree.
- `scripts/agent/install_git_hooks.sh` could not update the linked worktree's shared `.git/config`: `Read-only file system`. Manual pre-final checks are used instead.

First red run:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier_semantics.py -v
Ran 7 tests in 2.561s
FAILED (failures=3)
```

All three new executor tests failed with the intended message:

```text
missing compiler-backed executor: .../scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py
```

First green run after the executor was added:

```text
Ran 7 tests in 4.289s
OK
```

Second red run added report-level authentication for the executor hash, compiler route, and per-case compiler evidence. It failed because the old verifier accepted those mutations or missing evidence:

```text
Ran 7 tests in 3.304s
FAILED (failures=2)
```

The producer and verifier were then tightened to authenticate the executor file, backend pipeline, `mlir-opt`, `mlir-runner`, and compiler-evidence schema.

A third red/green cycle bound the exact Linalg-to-LLVM pass sequence before refactoring from a separately constructed scalar arithmetic module to direct JIT execution of the complete compiler-emitted tensor module. The red run reported the missing `linalg_to_llvm_pipeline`; executor-only tests after the refactor reported:

```text
Ran 3 tests in 3.863s
OK
```

The focused suite before the determinism regression reported:

```text
Ran 7 tests in 3.912s
OK
```

A final producer-determinism regression generated the same report path twice. Its red run showed byte differences only at the random temporary executor output suffix; after recording the stable `<temporary>/executor-results.json` placeholder, the regression reported:

```text
Ran 1 test in 8.890s
OK
```

The final complete focused suite, including that regression, reported:

```text
Ran 8 tests in 11.911s
OK
```

## Provenance bindings

The authenticated report binds:

- registered stage: `/nix/store/k2q1qg1xn0yvxx3bprvfq3dxphw8vz8m-tiny-stories-1m-kev-gpt-exact-torch.mlir`
- registered stage size: `7,608,283` bytes
- registered stage SHA-256: `e2e0fe83d874714847cdacc4918fc41220637569c8ac7ca225f0139ab82ea674`
- stage derivation: `/nix/store/han08nzx4rk44xwh2drcaqhn01k37f18-tiny-stories-1m-kev-gpt-exact-torch.mlir.drv`
- stage derivation SHA-256: `c9b704158300b53802d09f42aa20e065c90923a31a5818ef99be141cd66a185c`
- `torch-mlir-opt` SHA-256: `e1445e7540ef7bea2c29e5f36af8f0120e7b13f8fe0e78b01a21d2a0b7a8d9a9`
- `mlir-opt` SHA-256: `3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`
- `mlir-runner` SHA-256: `d501573e86911cb0b21f0ad307ea641431d5daf46b8f6b2a914888ca537f1d79`
- fixture file SHA-256: `2aadecfedbbf93a617890d21586d17456f945028d866c368c15af754471f3064`
- fixture self-hash: `4490ddcf0e6f59eed32ecfe31482dc142c9907f4e74efe32154a99d5651ef17f`
- executor SHA-256: `1c003ee2c638b37c27d57ff282c47654f7f07542949d25d35c846cf1cb261f4c`
- producer SHA-256: `8564a1773278ca425866b6a0e15ea572951e2e6dd1665d03104399f17f7efa61`
- decision self-hash: `429da5a367755d35bc38308589beaf25d291a8272ebf4d8944bfa4b8919ef8fe`
- probe file SHA-256: `645a87cdc4292ea584a04d4268187c612dd070b068036f9fa13b71865b36cbe6`
- probe self-hash: `cd4a4ca7a723eb1a19ad603fffad1cd345a04cd28d5062d89a50c4dd28d4f8a5`

The verifier continues to recompute the frozen Task 1--3 identities and Task 5 frontier bindings. No Task 1--3 identity value was changed.

## Exact semantic results

- `shift_one`: `ok`, `si64[5] = [-3, -1, 0, 0, 2]`
- `shift_zero`: `ok`, `si64[5] = [-5, -1, 0, 1, 5]`
- `shift_sixty_two`: `ok`, `si64[4] = [-1, -1, 0, 1]`
- `negative_shift`: `rejected_negative_shift`, `shift_contract:negative_shift`, compiler exit 1, no output
- `shift_greater_than_sixty_two`: `rejected_shift_greater_than_sixty_two`, `shift_contract:greater_than_sixty_two`, compiler exit 1, no output

Each valid record contains SHA-256 evidence for the exact Torch modules, frontend outputs, Linalg outputs, LLVM modules, and JIT stdout. Each invalid record contains the Torch module hash, compiler exit code, and compiler stderr hash.

## Negative coverage

The focused tests reject:

- detached registered stage bytes
- altered `torch-mlir-opt` bytes
- altered frontend pipeline
- altered Linalg-to-LLVM pipeline in the authenticated report
- altered `mlir-opt` binding
- altered executor hash
- duplicate fixture/report cases
- extra fixture/report cases
- missing fixture/report cases
- missing per-case compiler evidence
- invalid cases containing output
- nondeterministic report bytes caused by transient executor output paths

## Receipt correction

The first end-to-end producer invocation exposed a pre-existing one-character transcription error in `registered_stage_build_command_sha256`, introduced by commit `2702a718`:

- stale receipt value: `d33a21e9b4564e0e4ed14ec50bf08b7ccc3ed9c99b01b5ead0d5c792356354`
- canonical hash of the unchanged command array: `d33a21e9f8b4564e0e4ed14ec50bf08b7ccc3ed9c99b01b5ead0d5c792356354`

Only that binding, the producer binding required by the producer's changed live bytes, and the decision self-hash were refreshed. The build command and all frozen model identities remain unchanged.

## Files

- Created `scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py`
- Modified `scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py`
- Modified `scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py`
- Modified `tests/test_tinystories_1m_exact_frontier_semantics.py`
- Created `artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json`
- Refreshed live bindings in `artifacts/comparison/tinystories-1m-exact-frontier-decision.json`

## Verification commands

```text
nix develop -c python scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py --executor scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py --out artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py --probe-report artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier_semantics.py -v
```

All three completed successfully before commit.

## Review fix round 1/5: standalone trust reconstruction

Status: blocking provenance substitution finding fixed without changing model, compiler, fixture, executor semantics, producer, decision receipt, or canonical probe bytes.

### Reproduction

The committed verifier at `2c6373e` was exercised with two report mutations whose self-hashes were recomputed:

1. The reported stage artifact and derivation were replaced with the live `torch-mlir-opt` binary and its derivation.
2. The reported `mlir-runner` was replaced by detached copied bytes and `shift_one.compiler_evidence.runner_stdout_sha256` was replaced with 64 zeroes.

Both standalone verifier invocations returned exit 0 and `status: accepted`. This confirmed that file existence, report-selected hashes, and 64-hex evidence shape were internal consistency checks rather than independent provenance.

### Red tests

Three adversarial tests were added before the verifier change:

```text
nix develop -c python -m unittest \
  tests.test_tinystories_1m_exact_frontier_semantics.ExactShiftCompilerExecutorTest.test_verifier_rejects_stage_not_produced_by_declared_nix_build \
  tests.test_tinystories_1m_exact_frontier_semantics.ExactShiftCompilerExecutorTest.test_verifier_rejects_detached_mlir_opt_or_runner \
  tests.test_tinystories_1m_exact_frontier_semantics.ExactShiftCompilerExecutorTest.test_verifier_reexecutes_executor_before_accepting_case_evidence -v
```

Observed before implementation:

```text
Ran 3 tests in 2.195s
FAILED (failures=3)
```

Each failed because the expected `ValueError` was not raised.

### Implementation

Standalone/default `verify_probe_report` now reconstructs every trusted input independently:

- Revalidates the receipt's canonical registered-stage command hash.
- Runs the exact registered Nix build command from the repository root and requires exactly one output.
- Requires the report's stage path to equal that canonical build output path.
- Resolves the live stage derivation with `nix path-info --derivation` and compares report path and bytes/hash to it.
- Runs a fresh `nix develop` tool-resolution command for `torch-mlir-opt`, `mlir-opt`, and `mlir-runner`.
- Requires each independently resolved tool to exist in a Nix store derivation.
- Compares the report's exact tool paths and hashes against those independently selected binaries, never against report-selected bytes.
- Reconstructs and validates the canonical executor command.
- Re-executes the declared executor with the canonical stage, fixture, pipeline, and `torch-mlir-opt`; PATH is constrained to the independently resolved Torch-MLIR and MLIR tool directories.
- Compares replay schema, stage hash, fixture hash, tool hash, pipeline hash, complete compiler route, ordered case records, outputs, invalid no-output records, and every per-case compiler/JIT evidence hash to the report.

Synthetic unit tests inject explicit fake stage/tool/replay resolvers so they continue isolating individual report validation branches. These are keyword-only test seams; standalone/default verification always uses the live Nix-backed resolvers and executor replay.

### Green evidence

The original three adversarial tests after implementation reported:

```text
Ran 3 tests in 21.569s
OK
```

Direct pinned-tool substitution coverage was expanded to all three tools:

- detached `torch-mlir-opt` fails with `probe_tool_live_path`
- detached `mlir-opt` fails with `probe_mlir_opt_live_path`
- detached `mlir-runner` plus mutated stdout evidence fails with `probe_mlir_runner_live_path`
- live tool paths plus mutated stdout evidence fails after replay with `probe_executor_results`

The expanded pinned-tool regression reported:

```text
Ran 1 test in 18.674s
OK
```

The standalone verifier with independent reconstruction and replay returned exit 0 and preserved:

- canonical probe file SHA-256 `645a87cdc4292ea584a04d4268187c612dd070b068036f9fa13b71865b36cbe6`
- canonical stage SHA-256 `e2e0fe83d874714847cdacc4918fc41220637569c8ac7ca225f0139ab82ea674`
- exact three valid outputs and two invalid compiler rejections

### Decision receipt justification

This review fix does not modify `artifacts/comparison/tinystories-1m-exact-frontier-decision.json` or the producer, so there is no new producer/decision hash cycle.

The Task 2 decision changes in commit `2c6373e` remain required provenance bindings rather than semantic changes:

- `probe_producer_script_sha256` had to follow the producer's live bytes after it authenticated the newly exposed compiler route and canonicalized its temporary output path.
- `registered_stage_build_command_sha256` corrected the pre-existing one-character typo documented above; the unchanged build command otherwise failed the producer's pre-existing canonical hash check.
- the decision self-hash necessarily followed those two binding corrections.

No Task 1--3 identity, model/compiler/RTL input, pipeline string, fixture binding, stage bytes, or semantic expectation changed.

### Self-review

- Trust decisions occur against independently resolved paths before report-selected byte hashes are considered.
- Detached same-byte copies are rejected by exact live path comparison, not accepted because their content matches.
- Nix derivation existence is checked for the stage and every selected tool.
- Replayed cases are compared as the complete ordered JSON records, so changing any compiler or JIT evidence hash is detected.
- Invalid cases retain exact status/diagnostic and no `output` field because replay equality covers the complete records.
- The canonical report remains unchanged because verification is read-only.

### Final review-fix verification

```text
python3 -m py_compile scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py tests/test_tinystories_1m_exact_frontier_semantics.py
git diff --check
nix develop -c python scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py --executor scripts/pipeline/execute_tinystories_1m_exact_shift_semantic_probe.py --out artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py --probe-report artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier_semantics.py -v
sha256sum artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
```

Observed:

```text
standalone semantic probe: status accepted
standalone registered stage: status accepted
Ran 11 tests in 39.357s
OK
645a87cdc4292ea584a04d4268187c612dd070b068036f9fa13b71865b36cbe6  artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
```
