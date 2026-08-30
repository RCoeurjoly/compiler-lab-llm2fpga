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
and JIT-executed the compiler-emitted right-shift cases. For left shift, it used
live PyTorch plus the independent signed-si64 oracle and proved the generated
`arith.shli` lowering. The receipt
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
`9c70616e324be2be49e96de8aabf962c2050456f` produced byte-identical copies
of all eleven canonical files:

| Canonical evidence | SHA-256 |
| --- | --- |
| serialized receipt | `3fc642f55482fe88da58a725b44cc1f9c822786701a5187456a36190f13fb9f2` |
| receipt self-hash | `3181afd4bc1c6d72c2ecc64985f3fa949f7e87bbcedccabb6d6157dab47af441` |
| export log | `993972ee373fbef7b0d334fc180f1277dc9b61698df7c3ed4aaa17a8c63b74e2` |
| Torch log | `e7cf82e57bc7c28ec8a188c184528e2f9a54892d3154ab3de729ad7b9f0d04e0` |
| Linalg log | `076495c2b23b66fd2a20c8e4bec550c9f24304422cbb8b3c2ab3837938f5806f` |
| SCF log | `f1c3e00460f680c0186a9b275e30c1db560d6b75ab7968c8f092fd8f7a548de1` |
| Linalg `.drv` | `0651758665581517360aee0d6e137ccbb932fdab99946b5d43ef2fc85fa2f442` |
| canonical Linalg derivation JSON | `e042b4a49c46bacae9294a8d3d1a7f87fa797312cea98a40799c569f0e9f3f46` |
| SCF `.drv` | `103aaba38b6df8b4b28fe93781c095efa75e26c06ea586530f573b9f31127b7c` |
| canonical SCF derivation JSON | `feaf6061090a89f85cf030bb86dc163342c11370cc023dc322a7f50e3e7c5da3` |

Nix dirty-tree and cache/build progress messages are excluded from canonical
logs; substantive diagnostics, commands, exit codes, store results, artifact
bytes, exact derivation build-command text, referenced store-tool bytes, `.drv`
bytes, canonical derivation JSON, and hashes remain bound. The receipt also
binds the exact classifier SHA-256
`966541ca4d548a9f1f6820819c87add91aa401d025d3946ab5db69c39f3bf9e7`
and determinism-verifier SHA-256
`3fa8ac5fc7b406e0186587a9d8577d67d0e48a5a4e23be30ffabb3958ede6d3f`.
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
The superseded round-1 eleven-file capture remains preserved unchanged under
`artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf-v2`.
The superseded round-2 eleven-file capture remains preserved unchanged under
`artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf-v3`.
The bounded successor plan is
`docs/superpowers/plans/2026-08-30-exact-tinystories-scf-registration-frontier.md`;
it selects only the existing direct Linalg-to-SCF no-handshake registration
experiment and does not implement that registration here.

## Scope

No compiler, model, adapter, quantization, runtime, memory, scheduling, RTL, or
board change is included. The next bounded plan must address the registered SCF
availability frontier before any compiler or pipeline change is attempted.
