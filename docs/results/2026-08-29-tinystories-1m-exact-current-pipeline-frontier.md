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

Two independent classifier executions from code commit
`b6f54a4edec9d90a02c94ec79f8a9913f0a4cbdf` produced byte-identical copies
of all eleven canonical files:

| Canonical evidence | SHA-256 |
| --- | --- |
| serialized receipt | `e1ccda9f6042671660ab753d99fe8af9b77dd362b9afc0bedae1fc17f055ae60` |
| receipt self-hash | `d43c5adaf995c432ad31001cc86654025f5976e780d25951246aa5f4e5e14bf3` |
| export log | `993972ee373fbef7b0d334fc180f1277dc9b61698df7c3ed4aaa17a8c63b74e2` |
| Torch log | `e7cf82e57bc7c28ec8a188c184528e2f9a54892d3154ab3de729ad7b9f0d04e0` |
| Linalg log | `dedbd34b50cd1d6026d49d272a76d1ab0623bfea9c9b2e35a5eeb2a45f2d0ccd` |
| SCF log | `f1c3e00460f680c0186a9b275e30c1db560d6b75ab7968c8f092fd8f7a548de1` |
| Linalg `.drv` | `57c76eca7dbea3dc1058595f0524ac6fa0172b35c6266a9d989ebf29169700f7` |
| canonical Linalg derivation JSON | `9b1fc76bbe17c1a871c1b5f9e1c8012a46339291ffff33726e5368fb650e6f40` |
| SCF `.drv` | `103aaba38b6df8b4b28fe93781c095efa75e26c06ea586530f573b9f31127b7c` |
| canonical SCF derivation JSON | `feaf6061090a89f85cf030bb86dc163342c11370cc023dc322a7f50e3e7c5da3` |

Nix dirty-tree and cache/build progress messages are excluded from canonical
logs; substantive diagnostics, commands, exit codes, store results, artifact
bytes, exact derivation build-command text, referenced store-tool bytes, `.drv`
bytes, canonical derivation JSON, and hashes remain bound. The receipt also
binds the exact classifier SHA-256
`966541ca4d548a9f1f6820819c87add91aa401d025d3946ab5db69c39f3bf9e7`
and determinism-verifier SHA-256
`b875ea3bab84bcefe2ca52c887205623b3169abc61183ddb843eb3021f4e4c46`.
Verify both bundles with:

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
```

The current bundles live under
[`tinystories-1m-exact-frontier-determinism-scf`](../../artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf/manifest.json).
The earlier Torch and shift-frontier bundles remain unchanged and independently
verifiable; the new receipt binds the predecessor receipt hashes and the frozen
Task 1--3 identities.

The superseded seven-file SCF capture remains preserved unchanged under
`artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf-v1`.
The bounded successor plan is
`docs/superpowers/plans/2026-08-30-exact-tinystories-scf-registration-frontier.md`;
it selects only the existing direct Linalg-to-SCF no-handshake registration
experiment and does not implement that registration here.

## Scope

No compiler, model, adapter, quantization, runtime, memory, scheduling, RTL, or
board change is included. The next bounded plan must address the registered SCF
availability frontier before any compiler or pipeline change is attempted.
