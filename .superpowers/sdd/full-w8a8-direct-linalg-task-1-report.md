# Task 1 implementation report: full W8A8 Direct-Linalg route

## Scope

Task 1 exposes the registered `tinystories-w8a8` model through the Direct-Linalg,
no-handshake pipeline. Changes are limited to:

- `flake.nix`: added the public alias
  `tinystories-w8a8-via-linalg-no-handshake` with model
  `tinystories-w8a8`, frontend `linalg`, backend `calyx-native-sv`,
  `pipelineStagePackagesNoHandshake`, and `noHandshakeLinalgStages`.
- `tests/test_full_tinystories_w8a8_scout.py`: added the focused configuration
  regression test required by the task brief. The test asserts the complete
  Direct-Linalg route and rejects TOSA frontend/package selection in that alias
  block.

No changes were made to `nix/models.nix`, backend math passes, docs, task3,
or the existing user-owned `docs/glossary.md` edit. The existing Calyx math
scout pass remains out of scope.

## TDD evidence

The new regression test was added before the alias and run first:

```text
python3 -m unittest tests.test_full_tinystories_w8a8_scout.FullTinyStoriesW8A8ScoutTest.test_full_model_w8a8_has_public_linalg_no_handshake_alias -v
FAIL: AssertionError: unexpectedly None
```

The failure was the expected missing-alias failure. After adding the minimal
alias, the full focused test module passed:

```text
python3 -m unittest tests.test_full_tinystories_w8a8_scout -v
Ran 12 tests in 0.032s
OK
```

## Verification

The required Nix evaluation check passed after retrying with access to the host
Nix fetcher cache:

```text
nix flake check --no-build
all checks passed!
```

The final diff passed:

```text
git diff --check
```

## Self-review and concerns

The alias is adjacent to the existing full-model no-handshake alias and uses
the exact package set and stage list specified in the brief. The test's regex
scopes the positive and negative assertions to that alias block. The initial
unprivileged Nix check could not open `/home/roland/.cache/nix/fetcher-cache-v4.sqlite`;
the elevated retry passed. `--no-build` validates flake evaluation only and does
not build or execute the newly exposed route.

The unrelated pre-existing modification to `docs/glossary.md` was preserved and
is not included in the task commit.
