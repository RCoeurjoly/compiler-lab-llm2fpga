# Exact TinyStories-1M current-pipeline frontier

## Result

The authenticated registered pipeline accepts `pytorch-exported`, `torch`, `linalg`, and `scf`. Its first invalid stage is `flat-scf`. The registered build exits zero and emits:

```json
{"artifact":"flat.scf.mlir","blockers":"blockers.json","stage":"flat-scf","status":"completed-with-residuals"}
```

The classifier preserves but rejects both residual payloads, records `reason: null` and `artifact_accepted: false`, and stops before `calyx`. No SystemVerilog claim is made.

| Evidence | Bytes | SHA-256 |
| --- | ---: | --- |
| manifest | 118 | `8b15b5aeffa19ed20975926fab100d28398863482eccb3fcd6840a65ed2df7cb` |
| `flat.scf.mlir` | 18,933,168 | `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6` |
| `blockers.json` | 19,257,118 | `2be1745e4a588c533b03d792439d5698c90b7ecd2bb9dba2c5294791d94576f9` |

## Deterministic capture

Two sequential captures from committed code `c22c5f8d85e453a56b185f6238970933f5b1d407` are byte-identical across all 20 canonical files. Receipt file SHA-256 is `6af348b82f2e263980f0515f46b0a08c14898118d7e868cacfec3764ceae6acf`; self-hash is `961b81662493f1241eea58061433779314019e6c46a249022362d77fc61808c8`. The verifier independently resolves live registered derivations and compares payload paths, bytes, and hashes.

The prior-worker `/tmp/exact-scf-route-run-1`, partial, mixed-source, provisional `4f07`, and c22 cache-warm captures were quarantined. Only `/tmp/exact-scf-route-c22-final-run-1` and `-2` were promoted.

Tracked repo-source changes alter Nix source closure and derivation paths. Each verifier-only source commit forced another roughly six-hour SCF recompilation plus a roughly 40-minute blocker report. This packaging coupling should be addressed next.

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py --bundle-dir artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf
```

## Scope

No compiler behavior, model, adapter, route, RTL, host, network, credentials, or external system changed.
