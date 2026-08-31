# Task 3 report

The registered `flat-scf` output revealed a plan defect: its authoritative manifest is `completed-with-residuals` with nonempty `flat.scf.mlir` and `blockers.json`. Controller ruling required preserving and live-binding both payloads while rejecting the artifact and stopping before Calyx.

Commits `29578213d29ee14d557daef164ca8b4fbc2a3812` and `4f07c607717705401a8fdfd906f8a142910b8af7` added the exact schema, payload tests, and independent live verification. Real public verification exposed a replay-log defect: the classifier appends validation while the verifier compared only raw Nix output. Focused RED reproduced it; GREEN independently parsed the live manifest and reconstructed the exact suffix. Public verification then accepted all 20 provisional files, and 82 focused/adversarial tests passed. Commit `c22c5f8d85e453a56b185f6238970933f5b1d407` is the final code.

Fresh c22 captures `/tmp/exact-scf-route-c22-final-run-1` and `-2` are byte-identical and promoted. They stop at `flat-scf`, preserve manifest/residual/blockers, set `artifact_accepted=false` and `reason=null`, and do not run Calyx.

`/tmp/exact-scf-route-run-1` was prior-worker contaminated. All partial, mixed-source, provisional 4f07, and cache-warm captures were quarantined. Repo-source changes invalidated Nix source closure, forcing repeated roughly six-hour SCF recompilations plus flat-SCF reporting; this is a packaging-coupling concern, not a compiler change.
