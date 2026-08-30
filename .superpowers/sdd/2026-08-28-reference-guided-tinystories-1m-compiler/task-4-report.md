# Task 4 report: exact TinyStories compiler-model registration

## Result

Registered `tiny-stories-1m-kev-gpt-exact` through the unchanged `registerModel` stage graph with no backend overrides. The package is a pinned non-flake `kev-gpt-src` input at `df1fc45b2ffcb26fddc19cfd57621e7eedf6153f`; the derivation uses its Nix-store `model_packages/tinystories-1m` content alias. There is no `extra-sandbox-paths` configuration or `/home` build input.

The adapter authenticates any content alias by full file set, size, SHA-256, manifest, and receipt equality, and records canonical origin, materialized store path, and `complete_authenticated_package_file_identity`. The export verifies Tasks 1--3 before materialization and writes provenance afterwards; materializer receives no unsupported `--audit`.

## TDD and staging closure

Registration, alias/mutation, materializer CLI, isolated adapter load, and staged selection-authority tests were first made red. The staged selection test exposed an omitted authority. Preserved-sandbox inspection then showed that copying Nix-store paths retained hash-prefixed basenames. Explicit destinations now preserve the authenticated repository-relative layout for the selection document, reference artifacts, and comparison authorities. This is derivation-only staging, outside the Task 2 authenticated source closure; no Task 2/3 regeneration was needed for it.

## Final identities and verification

- Task 2 file/artifact: `173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a` / `af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838`
- Task 3 file/artifact/result: `e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3` / `9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3` / `c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644`
- `exported.pt2`: `6c9d2931a18811560f6565e9d313390fb5e0b7b167af39ddc094e19b949ce085`
- provenance manifest: `5119729faeeac04bb2504ac7134bbd32164af09459171fd44bc67a542572e27b`

Task 2 final regeneration took about two minutes. The final 3×16 Task 3 proof took about 34 minutes; highest sampled RSS was 3,502,228 KiB (not a measured peak).

```text
nix develop -c python -m unittest -v tests.test_tinystories_1m_exact_reachable_domain tests.test_tinystories_1m_exact_package_model tests.test_tinystories_1m_exact_pipeline_registration
Ran 33 tests in 126.243s — OK

nix build .#tiny-stories-1m-kev-gpt-exact-pytorch-exported -L
exit 0
```

The final manifest’s `exported_pt2_sha256` equals the actual export, records the canonical `/home/...` origin as provenance only, and records the Nix-store package as `materialized_path`.
