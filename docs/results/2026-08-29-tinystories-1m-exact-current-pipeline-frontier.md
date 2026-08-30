# Exact TinyStories-1M current-pipeline frontier

## Result

The authenticated registered pipeline now passes `pytorch-exported`, `torch`,
and `linalg`. Its first invalid artifact is the registered `scf` stage,
classified as `pre_calyx_frontier`:

```text
error: registered scf stage status is 'unavailable': baseline hardware pipeline lowers through CF and Handshake
```

The SCF Nix build exits 0 but emits only a 109-byte control manifest with
`"status":"unavailable"`. The classifier therefore rejects it rather than
treating exit status or partial output as validity. `flat-scf`, `calyx`, and
`calyx-native-sv` are not run in either canonical capture. No SystemVerilog,
syntax, synthesis, resource, timing, functional-equivalence, or board claim is
made.

## Hard semantic prerequisite

Before any derivation lookup or registered build, the classifier runs:

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py \
  --probe-report artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
```

The live verifier independently rebuilt and accepted the registered Torch
artifact (`e2e0fe83d874714847cdacc4918fc41220637569c8ac7ca225f0139ab82ea674`)
and replayed the compiler-backed right/left shift semantic proof. The receipt
binds the verifier bytes and semantic probe file SHA-256
`645a87cdc4292ea584a04d4268187c612dd070b068036f9fa13b71865b36cbe6`.

## Registered sequential execution

Both canonical runs invoke exactly:

```text
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-pytorch-exported
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-linalg
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-scf
```

All four commands exit 0. Artifact validity is true for the first three and
false for SCF after manifest validation. The stage order and exclusion of all
later stages are explicit in the self-hashed receipt.

## Full input and minimal reproducer

The complete 13,274,515-byte Linalg input is preserved as deterministic gzip:

| Evidence | SHA-256 |
| --- | --- |
| full Linalg input bytes | `f4792aef4a0054386bf4e9e6399cc107e6d947b4d608e97e6041ccdf2ffb59c8` |
| deterministic gzip | `1e6d47462458fed298353e97bfbc030af8c6b9e8f8a870e53fbd4d35ffe88594` |
| 109-byte SCF manifest reproducer | `afc3d62b34d2eda0ec241556e04ce2c36642ca6520609df7a2a2ef87b8ce7c7c` |

The frontier is a registered-stage availability decision, not an MLIR
operation legalization failure. There is therefore no exact operation/type
pair to reduce; the stage manifest is already the minimal diagnostic
reproducer.

## Deterministic capture

Two independent classifier executions produced byte-identical copies of all
seven canonical files:

| Canonical evidence | SHA-256 |
| --- | --- |
| serialized receipt | `1d1fd8eeea5ad5114ec36a5aea13c5b84cec4a60cc25fa2aa5793ed9e46bf8ce` |
| receipt self-hash | `7451d19a9dd7d10ae61e7759422625de300e3a5e4ae5b1b44dbc56d8f3173425` |
| export log | `993972ee373fbef7b0d334fc180f1277dc9b61698df7c3ed4aaa17a8c63b74e2` |
| Torch log | `e7cf82e57bc7c28ec8a188c184528e2f9a54892d3154ab3de729ad7b9f0d04e0` |
| Linalg log | `93b47b1f952a4128c6cdd2cab11fe000d78152d1b39d598c1e275bf463051a0d` |
| SCF log | `f1c3e00460f680c0186a9b275e30c1db560d6b75ab7968c8f092fd8f7a548de1` |

Nix dirty-tree and cache/build progress messages are excluded from canonical
logs; substantive diagnostics, commands, exit codes, store results, artifact
bytes, derivations, and hashes remain bound. Verify both bundles with:

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
```

The current bundles live under
[`tinystories-1m-exact-frontier-determinism-scf`](../../artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf/manifest.json).
The earlier Torch and shift-frontier bundles remain unchanged and independently
verifiable; the new receipt binds the predecessor receipt hashes and the frozen
Task 1--3 identities.

## Scope

No compiler, model, adapter, quantization, runtime, memory, scheduling, RTL, or
board change is included. The next bounded plan must address the registered SCF
availability frontier before any compiler or pipeline change is attempted.
