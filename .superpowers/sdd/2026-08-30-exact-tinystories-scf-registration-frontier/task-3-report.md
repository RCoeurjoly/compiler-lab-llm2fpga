# Task 3 report

The registered `flat-scf` output revealed a plan defect: its authoritative manifest is `completed-with-residuals` with nonempty `flat.scf.mlir` and `blockers.json`. Controller ruling required preserving and live-binding both payloads while rejecting the artifact and stopping before Calyx.

Commits `29578213d29ee14d557daef164ca8b4fbc2a3812` and `4f07c607717705401a8fdfd906f8a142910b8af7` added the exact schema, payload tests, and independent live verification. Real public verification exposed a replay-log defect: the classifier appends validation while the verifier compared only raw Nix output. Focused RED reproduced it; GREEN independently parsed the live manifest and reconstructed the exact suffix. Public verification then accepted all 20 provisional files, and 82 focused/adversarial tests passed. Commit `c22c5f8d85e453a56b185f6238970933f5b1d407` is the final code.

Fresh c22 captures `/tmp/exact-scf-route-c22-final-run-1` and `-2` are byte-identical and promoted. They stop at `flat-scf`, preserve manifest/residual/blockers, set `artifact_accepted=false` and `reason=null`, and do not run Calyx.

`/tmp/exact-scf-route-run-1` was prior-worker contaminated. All partial, mixed-source, provisional 4f07, and cache-warm captures were quarantined. Repo-source changes invalidated Nix source closure, forcing repeated roughly six-hour SCF recompilations plus flat-SCF reporting; this is a packaging-coupling concern, not a compiler change.

## Review fix round 1

The v5 verifier now rejects recomputed-self-hash lies in every stage and execution semantic field reviewed: status, terminal diagnostics, artifact size, upstream identity, invocation, result, route, frontend, backend, artifact acceptance, stage order, and the top-level diagnostic. Expected values come from the pinned c22 Git commit and cached registered derivations. The verifier authenticates c22 as a commit, requires Task 4 and registration ancestry, reconstructs all critical-input Git blobs and hashes, resolves the c22 flake archive and Nix derivation source identities, and authenticates the c22 classifier and verifier bytes. The running verifier is newer than c22 and makes no claim that its new bytes produced the receipt.

Default verification now also requires the public receipt to be byte-identical to both bundle receipts and requires the 19-file `reproducers/flat-scf` projection to be an exact regular-file, byte-identical projection of both canonical bundles. Adversarial public-path tests cover altered payloads, extra/missing files, symlinks, subdirectories, and nonregular entries.

The three immutable generated `flat.scf.mlir` paths alone are marked `-diff`; ordinary MLIR remains text-diffed. Their bytes remain unchanged at SHA-256 `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`.

The blocker census was not independently regenerated. The registered reporter took roughly 40 CPU-minutes and rerunning or reimplementing its census would either duplicate that cost or define new census semantics. Its report is therefore described only as the authenticated registered `blockers.json`: exact live path, bytes, and SHA-256 are independently verified; census meaning is not independently claimed.

## Review fix round 2

The v5 verifier is now fail-closed over the complete preserved receipt schema. Exact key sets cover the top-level receipt, claims, capture tools, semantic evidence, frozen and predecessor identities, pipeline execution, each stage and tool-revision object, each registered execution and derivation-tool binding, full input, control-manifest frontier evidence and minimization, and every pipeline-source identity object. The v3 bundle manifest, run records, comparison record, and file bindings are also closed to missing or unversioned extra fields.

Every executed-stage log now has one canonical public path and is bound independently to the exact bundled bytes, byte count, SHA-256, live replay semantics, and the matching stage/execution fields. Stage tool revisions are reconstructed exactly from the pinned c22 source commit and live registered derivations. Claims are the exact seven-key c22 object with every value `false`: no functional equivalence, resources/timing, syntax, synthesis, Calyx-native-SV, board inference, or backend/model/quantization/DDR/PCIe change is claimed.

Public end-to-end adversarial tests recompute receipt self-hashes and bundle bindings while mutating log paths/counts/payloads, tool revisions, every claim flag, and representative missing/extra keys throughout the nested schema. The immutable c22 compiler evidence and Git objects were not changed or regenerated.

## Review fix round 3

The v5 schema gate now validates exact JSON types recursively before source resolution, receipt self-hash canonicalization, or semantic value comparisons. Objects and arrays must be exact JSON objects and arrays; strings, booleans, integers, and nulls are distinct. All byte counts, sizes, and exit codes are nonnegative integers that exclude booleans and floats. The signed semantic probe output is the sole signed-integer list. No v5 float is schema-valid, so finite floats, `NaN`, and infinities are rejected without defining new numeric semantics.

The strict type walk covers receipt and bundle manifests, every stage and registered execution, logs and artifacts, claims, pipeline execution, full input, frontier/control-manifest/minimization and residual bindings, capture tools, semantic evidence, frozen/predecessor identities, pipeline-source critical inputs and derivation identities, tool bindings, and every nested list element. The preserved control manifest is also type-checked before its status branch is interpreted.

Public end-to-end adversarial tests use recomputed finite receipts and a permissively recomputed attacker hash for non-standard nonfinite JSON. They require causal `VerificationError` type/range rejection for bool/int/float confusion, negative counts, string/null/list/dict swaps, nested element mutations, `NaN`, infinity, and bundle file-manifest type lies. The c22 evidence remains byte-unchanged and was not regenerated.
