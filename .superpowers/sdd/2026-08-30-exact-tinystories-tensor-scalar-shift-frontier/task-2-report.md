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
