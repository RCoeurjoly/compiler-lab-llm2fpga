# Task 4 report: exact TinyStories compiler-model registration

## Result

Registered `tiny-stories-1m-kev-gpt-exact` with the existing `registerModel` stage graph and no backend overrides. Its export command invokes `TinyStories/model_adapter_exact_package.py` with explicit contract, package, and model paths.

A Nix-generated Python preflight verifies Task 1 contract/audit, canonical package manifest, Task 2 artifact/receipt, and Task 3 generation artifact/result hashes before the generic materializer can create `exported.pt2`. It then writes `exact-provenance-manifest.json`, including all bound identities and the exported-program digest.

No backend pass, model semantics, DDR3, PCIe, or stage graph was changed.

## TDD record

The focused registration test was added before the registration and failed with the expected missing-key error:

```text
KeyError: 'tiny-stories-1m-kev-gpt-exact'
```

After registration it checks the canonical manifest hash, all Task 1--3 receipt identities, empty `backend_overrides`, and the unchanged public pipeline stage set.

## Verification

```text
nix eval .#packages.x86_64-linux.tiny-stories-1m-kev-gpt-exact-pytorch-exported.name
"tiny-stories-1m-kev-gpt-exact-pytorch-exported"

nix develop -c python -m unittest tests/test_tinystories_1m_exact_pipeline_registration.py -v
Ran 1 test — OK

git diff --check
exit 0
```

The requested export-only build correctly failed closed before `exported.pt2` could be written. Its remaining blocker is environmental, not an identity mismatch: the authenticated package is frozen at `/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m`, but the Nix build user cannot traverse `/home/roland` (mode `750`). Without trust, Nix ignores the deliberately narrow `extra-sandbox-paths` declaration; with `nix build --accept-flake-config .#tiny-stories-1m-kev-gpt-exact-pytorch-exported -L`, sandbox setup fails with:

```text
getting status of '/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m': Permission denied
```

Nix Python independently verified the frozen manifest SHA-256 `374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35`. Changing home-directory permissions was not authorized and was not performed.

## Concern

Completing the export derivation needs a secure, read-only way to expose only the canonical package path to the Nix build user (and trust the flake's scoped sandbox path). Until then, the preflight correctly prevents a provenance-bearing exported artifact from being produced.
