# Task 6 report: exact frontier decision checkpoint

## Decision

Selected exactly one permitted response class: `compiler_pass`.

Task 5's accepted receipt commit is
`3418f989fec7996561f4e59ba6a6d902c1fb02a5`; its on-disk receipt file hash is
`b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55`.
The reduction isolates
`torch.aten.bitwise_right_shift.Tensor_Scalar` over signed `si64` tensor input
and scalar shift. The pinned Torch-MLIR source has no scalar overload and
rejects the generic operator during `export_and_import`'s Torch backend
pipeline, before project-side downstream passes can run.

The next task must therefore make a narrow Torch-MLIR frontend/legalization
change that lowers only the in-contract operation to a sign-preserving
arithmetic right shift, keeps `i64` width, broadcasts scalar shifts, rejects
out-of-range shifts, and leaves the adapter's explicit rounding sequence
untouched. It must not mutate model identity, package, export graph, backend,
runtime, scheduling, or RTL.

## Evidence and regressions

The decision receipt is
`artifacts/comparison/tinystories-1m-exact-frontier-decision.json`; the
human-readable record is
`docs/results/2026-08-29-tinystories-1m-exact-frontier-decision.md`.
They retain all Task 1--3 identity/generation hashes, the minimal reproducer
hash, Task 5 receipt/self hashes, precise red commands, and prospective green
criteria for both the reproducer and registered stage.

Fix round 1 adds the hash-bound signed-si64 semantic fixture
`artifacts/comparison/tinystories-1m-exact-shift-semantics.json` (file hash
`2aadecfedbbf93a617890d21586d17456f945028d866c368c15af754471f3064`). It
requires scalar-broadcast arithmetic shifts for `[-5, -1, 0, 1, 5] >> 1`,
shift-zero identity, and a valid shift of 62; it rejects `-1` and `63` with
named statuses and diagnostics. The decision now requires an evaluated lowered
result file, exact dtype/shape/value hashes, and a full-stage verifier that
checks all current Task 1--3 file/payload/result hashes against the decision
before accepting a nonempty Torch stage artifact. Compilation-only success is
not a green result.

Validation run for this checkpoint must include:

```text
nix develop -c python -m json.tool artifacts/comparison/tinystories-1m-exact-frontier-decision.json
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier_semantics.py -v
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py
```

## Fix round 2: provenance-bound semantic probe

The decision no longer accepts a detached lowered-result JSON. Its prospective
green gate uses the checked-in
`scripts/pipeline/run_tinystories_1m_exact_shift_semantic_probe.py` producer,
which builds the registered exact Torch stage, captures the concrete Nix stage
artifact and derivation, resolves `torch-mlir-opt`, and invokes the declared
future executor contract with the fixture and exact pipeline. The producer
writes only a canonical, self-hashed probe report. The report carries hashes
for the stage artifact, derivation, producer script/command, tool binary and
pipeline, executor command, fixture, and decision.

The verifier recomputes the decision canonical self-hash and Task 5
receipt/self/reproducer bindings before semantic acceptance. It then rejects a
report unless its on-disk stage artifact, resolved derivation, producer script,
tool binary, pipeline, report hash, and fixture all match the decision. It also
requires the record count and ID set to exactly equal the fixture, rejecting
duplicates, extras, and missing cases. Adversarial unit coverage verifies wrong
stage, producer, tool, pipeline, decision hash, stale report hash, and each
record-set failure. The executor remains a follow-up compiler-pass deliverable;
Task 6 supplies no compiler implementation.

No compiler or model implementation is included in Task 6.
