# Task 3 implementer report

## Base and implementation head

- Base: `2dff7ec5ecfd820bf5d6f588e49a93c233a59177`
- Initial implementation: `37347ddf4a60ee58ebcc3837ebb190b0f835c38f`
- Initial report: `f3bc741ebb08062ed06db07de37c7b42575607fa`
- Review-fix implementation heads: `6f7a8b3` (authentication/replay) and
  `7a1a0c0` (explicit shape/layout/access proofs)

## RED

Before the evaluator, verifier, evidence directory, evaluation JSON, or result
document existed, the required command

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_pass.py -v
```

failed with five explicit missing-production-surface failures. Nine behavioral
tests were skipped only because their evaluator/evidence prerequisites were
absent. No pass execution occurred before this conclusive RED.

Two later defects also received focused behavioral REDs before their fixes:

- the representative run exposed that Task 2's complete-contract summarizer
  rejects a valid post-pass census with eliminated classes; a zero-tolerant
  census test failed before the evaluator was corrected;
- an independently rehashed operation-census mutation was accepted by the
  verifier; the focused adversarial test failed before independent complete
  and representative census recomputation was added.

Review fix round 1 began with a second conclusive RED. Full-rehashed attacks
showed that the old verifier accepted `/bin/true` as its Task 2 launcher,
rebound model/Task-1-through-3/provenance data, three parse-check fields, all
five reproducer execution fields, and semantic-evidence mutation because no
live probes existed. A representative-byte rebound also reached the wrong
trust boundary. The corresponding adversarial tests failed before production
changes and are retained in the 19-test suite.

## Exact identities and provenance

- Task 2 contract: 4,277,281 bytes,
  `c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910`.
- Retained c22 flat-SCF input: 18,933,168 bytes,
  `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`.
- Pinned `mlir-opt`: 496,904 bytes,
  `/nix/store/qfhb8ajk2kw32lrmk8xqaa1g6h7w95p8-mlir-21.1.2/bin/mlir-opt`,
  `3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`.
- Existing pass plugin: 21,714,240 bytes,
  `/nix/store/p01jw41h2jm2pr8xxww3acrjgx5rl1qn-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`,
  `6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744`.
- Exact pipeline:
  `builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`.

The evaluator and verifier now use the current trusted interpreter to run the
exact Task 2 verifier. The verifier independently compares the complete model,
Task-1-through-3 identities, c22/current derivations and outputs, unrealized
current-alias provenance, and every representative binding against the
authenticated contract. It never delegates trust to the interpreter recorded
inside the mutable evaluation payload. Every input binding was identical
before and after its pass invocation.

## Representative results

All representatives ran, parsed, and were recorded before the complete input.

| Class | Classification | After class count | Pass time (ns) | Output SHA-256 |
| --- | --- | ---: | ---: | --- |
| `memref.collapse_shape` | `eliminated` | 0 | 37,099,911 | `3e20c196c823cf15079740ae1385519fd075bd5b66ec5151dbb6419157609c66` |
| `memref.copy` | `preserved` | 1 | 39,211,045 | `bc331bbe83d22a803d9ea92683738141aac5ed14bf20e87c5f188731d20f125c` |
| `memref.expand_shape` | `eliminated` | 0 | 36,501,631 | `a739daf1be198edb9ad0c024715672b8ccc417c0fc698a1af94f627015483726` |
| `memref.reinterpret_cast` | `eliminated` | 0 | 39,329,232 | `a739daf1be198edb9ad0c024715672b8ccc417c0fc698a1af94f627015483726` |

Each run retains exact stdout, stderr, output, parse-check streams, command,
exit, elapsed nanoseconds, and byte identities. The verifier independently
reconstructs the parse command and compares fresh exit/stdout/stderr exactly.

## Semantically live representative probes

Four additional executions, still before the complete artifact, use the exact
authenticated selected operation with live `memref.load` and `memref.store`
uses. Both evaluator and verifier independently derive shape, strides, offset,
element count, and linear memory-access maps from the before/after IR.

| Class | Before shape/layout | After shape/layout | Linear load/store | Status |
| --- | --- | --- | ---: | --- |
| `memref.collapse_shape` | `4x256`, `[256,1]`, offset 0 | `1024`, `[1]`, offset 0 | 515 / 515 | `proven` |
| `memref.copy` | `1`, `[1]`, offset 0 | `1`, `[1]`, offset 0 | 0 / 0 | `proven` |
| `memref.expand_shape` | `1x1`, `[1,1]`, offset 0 | `1`, `[1]`, offset 0 | 0 / 0 | `proven` |
| `memref.reinterpret_cast` | `1`, `[1]`, offset 0 | `1`, `[1]`, offset 0 | 0 / 0 | `proven` |

The collapse probe preserves 1,024 elements; the other probes preserve one.
Semantic-evidence mutations are rejected by independent recomputation.

## Complete retained c22 result

Exact before census:

| Class | Count | Unique signatures |
| --- | ---: | ---: |
| `memref.collapse_shape` | 4,682 | 450 |
| `memref.copy` | 3,228 | 27 |
| `memref.expand_shape` | 921 | 10 |
| `memref.reinterpret_cast` | 11,449 | 408 |
| Total | 20,280 | 895 |

The full invocation ran for 885,060,069 ns and exited 1. It produced exact
empty output (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`)
and 791 exact stderr bytes (SHA-256
`2348676f655fc6c8892dac898f1461ef6faf53b091b8b1d2e3efee3adf15e4b7`).
Therefore there is no parseable post-pass artifact and the four after counts
are recorded as unavailable, not falsely reported as zero. All 895 registered
input signatures are fail-closed as `new_invalid` for this invalid full run.
The full invariant status is `unavailable_due_invalid_output`; it is not a
parseability-derived preservation claim and independently blocks registration.

The earliest diagnostic-emitting canonical signature is the source operation
at retained c22 line 2,389:

- operation: `memref.subview`;
- signature SHA-256:
  `6149b92a9d179ef65caa53ff8dd33259b3d0c05085e5289384627b80c931f693`;
- diagnostic: `expected 1 offset values, got 2`.

The existing pass flattens `%arg2` from `memref<64x64xi64>` to
`memref<4096xi64>` while leaving the rank-2 subview offsets/sizes/strides
unchanged. The 200-byte one-operation exact reproducer independently exits 1
with the same diagnostic; its measured pass time was 40,305,841 ns. Its exact
command, exit 1, stdout, stderr, absent-output observation, and retained empty
output bytes are independently reconstructed and replayed. Elapsed time is a
positive authenticated observation only and is deliberately excluded from
replay equality and semantic decisions.

## Decision

`compiler_pass_extension`

The zero-blocker registration gate is not satisfied because the complete run
has no valid parseable output and introduces the exact invalid subview
signature above. No stage was registered, no Calyx command ran, and the pass
was not modified. The bounded follow-up is an extension for only this
ranked-static-argument/subview interaction with a before/after semantic
regression; float-math work remains out of scope.

## Canonical evidence

- Evaluation self-hash:
  `f3e6bebf28c6795ce54d8e59189c6ef73bce48e121353ae819f36eeb68a79651`.
- Evaluation file: 225,078 bytes,
  `463f1d141a99adfda6a806ac6de55b309e9e3ca76e03631d2908ddc92a21d490`.
- Exact representative/full streams:
  `artifacts/comparison/tinystories-1m-exact-memref-pass-evidence/`.
- Exact minimal residual:
  `reproducers/tinystories-1m-exact-flat-scf-memref/task3-earliest-remaining/`.

## GREEN

- Public verifier:
  `nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py`
  — `PASS`, with `compiler_pass_extension` and unavailable post-pass counts.
- Required suite:
  `nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_pass.py -v`
  — `Ran 19 tests in 137.332s`, `OK`.
- Python compilation for evaluator, verifier, and tests — PASS.
- `nix flake check --no-build` — PASS (`all checks passed`).
- Staged `git diff --check` — PASS after marking raw byte evidence non-diffable;
  no evidence bytes were normalized.
- Repository pre-commit hygiene hook accepted `6f7a8b3` and `7a1a0c0`.

## Files

- `.gitattributes` (only the new raw-evidence paths are marked non-diffable)
- `scripts/pipeline/evaluate_tinystories_1m_exact_memref_pass.py`
- `scripts/pipeline/verify_tinystories_1m_exact_memref_pass.py`
- `tests/test_tinystories_1m_exact_memref_pass.py`
- `artifacts/comparison/tinystories-1m-exact-memref-pass-evaluation.json`
- `artifacts/comparison/tinystories-1m-exact-memref-pass-evidence/`
- `docs/results/2026-08-31-tinystories-1m-exact-memref-pass.md`
- `reproducers/tinystories-1m-exact-flat-scf-memref/task3-earliest-remaining/`

No compiler pass source, runtime script, Nix pipeline registration, Calyx
source, model source, or authenticated Task 2 input was modified.

## Residual risks

- The current protected alias remains unrealized. This task intentionally
  evaluates retained authenticated c22 bytes plus Task 2's explicit
  runtime-byte-equivalence provenance.
- A failed MLIR pass leaves no valid output census. Evidence is fail-closed:
  after counts are unavailable and all registered input mappings are
  `new_invalid`; they must not be interpreted as transformations observed to
  completion.
- The identified subview is the earliest emitted diagnostic and the exact
  minimal reproducer. Other interactions may appear after it is fixed; they
  were not speculatively classified here.
- Elapsed times are exact observations for this run, not performance promises.
