# Task 3 report: authenticated exact frozen generation

## Status

Implemented and verified. Three fresh `ExactModelBundle` instances each generate
the exact frozen sixteen-token sequence from prompt IDs `[7454, 2402, 257, 640]`:

```text
[11, 612, 373, 257, 1310, 2576, 3706, 20037,
 13, 1375, 6151, 284, 711, 2354, 287, 262]
```

Every eager and exported tensor is compared at every step for context lengths
4 through 19. The proof performs 16 shape-specific exports and 48 exported
replays. No model semantics, arithmetic profile, backend, DDR3, PCIe, board
integration, or compiler-model registration was changed.

## Fail-closed authority

Before any export or eager candidate execution, the verifier now authenticates
complete canonical equality of every live bundle component against its on-disk
and Task 2 authority:

- Task 1 contract and audit, including audit self-hash;
- Task 2 fixed Q/DQ profile and reachable-domain certificate, including their
  self-hashes and file identities;
- the package manifest at the origin authenticated by the contract and Task 2;
- the independent fixed-logits oracle and the entire live `oracle_logits`
  tensor;
- the Task 2 receipt, including all nested execution/oracle fields and receipt
  self-hash;
- all 257 live model-state tensors by name, dtype, shape, raw bytes, canonical
  tensor-manifest hash, and Task 2 named-state digest.

The accepted identities are Task 1 commit
`c8eb2011ee09c368accdf8efd67c50dfc5564679` and Task 2 commit
`a2eda783819bbfb35a833d1a45d3dd125a176973`. Authority data recorded in the
Task 3 artifact is derived only from already validated disk objects; no
unvalidated live identity is copied into the authority.

Adversarial tests consistently rehash nested mutations in the contract, audit,
fixed profile, reachable certificate, manifest, independent oracle, oracle
logits, and receipt. Each mutation fails before generation. A live model-buffer
mutation with an unchanged receipt is rejected as `task_2_model_state_mismatch`.

## Exported state and execution proof

`_TraceOutputs` adds exactly one proven wrapper prefix, `model.`, to exported
state names. For every context-length export the verifier removes only that
prefix, rejects any absent/unproven prefix or name collision, then derives the
canonical name/dtype/shape/bytes manifest. Every export must match the complete
authenticated Task 2 model state before it can be replayed.

The normalized model-state tensor-manifest SHA-256 is:

```text
1f56e70699f45f702b6a765960b60246f13a5a8d74f53d318b1a1e9839f66403
```

The Task 2 named-state SHA-256 is:

```text
0c55aba9769d1cf836cb9fae7d39e9ea1ce8cef2e2e617acbe1cd465e2b16c66
```

Sharing the shape-specific exports across the three fresh runs is permitted
only after every fresh bundle independently passes the same complete authority
and state proof. Each of the 48 replays directly compares all 386 returned
tensors with `torch.equal`, including:

- full context logits and the current 50,257-element logits vector;
- 12 block-0 checkpoints;
- 97 Q/DQ groups, each with codes, scales, and dequantized values;
- 49 serial GEMV accumulator tensors;
- 33 nonlinear-boundary tensors.

The canonical named observation hashes are also compared. Greedy selection
explicitly finds all IDs equal to the maximum and chooses the smallest ID.

## Compact authenticated artifact

The v2 artifact stores one canonical named evidence set for each of the 16
common trajectory steps. Successful per-mode/per-run records retain only step
evidence digests, counters, references to the canonical evidence, transcript
hashes, run hashes, and generated tokens. Full dual eager/exported evidence is
stored only on a mismatch. The generator still computes and compares every
tensor in every replay before producing this summary.

The artifact shrank from 4,654,703 bytes to 954,676 bytes. Its final identities
are:

```text
artifact self SHA-256: 2e4f35b2875127bff7d74bcdc404edd3afad1c8fc6693dca05cd7a1636b22b69
artifact file SHA-256: b15fe696a21b8fa9ddf0ae17c6cc264c8cac0dbbdd51880b924452de5d388762
generation result SHA-256: 3113e57cc016292804beb2e35e6443ca8fc7cd1439272abde0cb62edc1c77524
export-cache SHA-256: 6e3fcc27e15b215ad3a7f7c4490003809f46fba6c69d2460dc271723f5112613
```

All three transcript hashes are identical:

```text
2a0a0bf878c3a3774e108b780f4ab38fb59695bdd59201489db4df6e4f3cbb38
```

The three-run aggregate is
`8a1c001212d5922cbd6ede9bf532c316b6a63dde85f7ccd9576476bfba4e2b62`.
The run hashes, which also bind deterministic run indices, are:

```text
d4051da20773937685bad41ee1aa24e3972f5f4fbf5bc846066f4ff84976e1ca
6085530b3f1d95554f3eb9299005dca87ca35e6b16b7d93aecb6e1e8ab06b785
9b954be2d24be2acdeb6a19d14424db548354925d8630b48dd45f42040b2025d
```

The verifier and test source hashes embedded in the artifact are:

```text
verifier: bc615fd47b7b224198be9ea7a4e88aff2797df993bf2979e5b1de19447722d2b
tests:    92e129e2d216ac71ccb70c422975d858e5e286ecd0fbccc5727c20c32e72c2c0
```

Offline validation rederives the artifact self-hash, source hashes, schema,
Task 1/2 identities, complete compact-evidence hashes, all per-mode aggregates,
counters, transcripts, run hashes, and generation result root. A consistently
rehashed later-step observation changes the aggregate digest and is rejected.
Artifact tests do not require the external package or model snapshot; only the
expensive reproduction is conditional on those paths.

`completed_runs` counts a run only when it has all 16 expected tokens, exactly
16 matched steps, and no mismatch. A cheap regression covers full-token but
partial-step, partial-token, and early-mismatch cases.

## TDD record

The review fixes were implemented through focused red/green cycles:

- complete live-component mutations initially passed for seven previously
  ignored identities; the completed authority closure rejects all of them;
- normalized export-state and mode-aggregate tests initially failed because
  their helpers did not exist, then passed after canonical binding was added;
- the partial-run regression initially failed because completed-run accounting
  did not exist, then passed after exact completion criteria were added;
- the offline compact-artifact suite failed against the old 4.65 MB v1 artifact
  on size, schema, mode summaries, and normalized export binding, then passed
  against the generated v2 artifact.

The final cheap/offline/authentication gate ran 11 tests in 0.935 seconds and
passed. It includes independently rederived aggregate hashes and consistently
self-rehashed drift tests.

## Verification and timing

Single final artifact generation:

```text
nix develop -c python scripts/comparison/verify_tinystories_1m_exact_generation.py ...
elapsed=1690.30s maxrss=4234884KB
```

The authenticated result root was then pinned and only the verifier source and
artifact self-hashes were deterministically rebound; the three full model runs
were not repeated for this mechanical rebind.

Final full Task 3 reproduction suite:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_generation.py -v
Ran 16 tests in 1848.862s — OK
elapsed=1857.93s maxrss=4352476KB
```

Final Task 2 authority regressions:

```text
nix develop -c python -m unittest -v \
  tests.test_tinystories_1m_exact_reachable_domain \
  tests.test_tinystories_1m_exact_package_model
Ran 24 tests in 119.780s — OK
elapsed=126.99s maxrss=1317992KB
```

## Concerns

- The full proof remains intentionally expensive: approximately 31 minutes and
  4.35 GB peak RSS for the final suite, because all 16 static shapes and all
  observation tensors are recomputed.
- The expensive reproduction depends on the immutable external package and
  Hugging Face snapshot at the Task 1/2 paths. Offline artifact integrity and
  mutation tests remain available when those external paths are absent.
