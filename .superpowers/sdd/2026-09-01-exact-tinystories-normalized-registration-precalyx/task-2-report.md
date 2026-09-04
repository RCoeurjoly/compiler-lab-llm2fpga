# Task 2 report: exact normalized registration and preparation only

## RED/GREEN

- RED: the Task 2 unittest file failed before implementation because the exact flake alias was absent.
- GREEN: `nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L` built `/nix/store/azz64q7fcbbsqyja72mkryfdjkgqrvk4-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.
- GREEN: the independent verifier recomputed c22/plugin/normalized/prepared/receipt hashes, parser identity, parses, raw zero counts, legality self-hash, and checker replay.
- GREEN: five registration/no-Calyx unittests passed, including stale identity/output, false-legality, pipeline, and file-scoped closure mutations.

## Outputs and frontier

- `flat.scf.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- `pre-calyx.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- legality file / receipt: `8c27b2419fd37434b360fd98b0fcdbc2b929767a9501f33ef05780c339c3e079` / `ad16079fd1fccf83d837507b526048dce4c87e0fa5744b9293e48bdd9d4a732c`
- prepared legality: blocked; `math.floor` 1376 at line 422, column 18; `arith.negf` 1369; `math.absi` 1156.
- `calyx_authorized`: false. No CIRCT, Calyx, SV, synthesis, or board command ran.

## Concerns

The stage is intentionally blocked at the observed prepared legality frontier.
Storage reached capacity during the task; only an unused user cache and an
unused process-unreferenced Nix shell scratch directory were cleared. Nix
temporary/cache activity was redirected to `/dev/shm`.

Commit: recorded with this Task 2 change.

## Fix round 1: authority and replay hardening

Review found that a coherent parser-clean replacement and a manifest-selected
checker stub could make the old verifier accept `calyx_authorized: true`. The
verifier now resolves c22, plugin, pinned `mlir-opt`, commands, the tracked
checker, and Nix-materialized checker from the flake-owned derivation
authority—not from the bundle manifest. It verifies tracked/materialized
checker bytes after the three parser-identity substitutions, then replays both
normalization and the exact no-scout preparation pipeline in `/dev/shm` and
byte-compares each result to the candidate bundle before replaying the bound
checker.

New REDs constructed both coherent attacks in temporary bundles. Both were
accepted by the old verifier and are rejected by the hardened verifier. The
test suite also creates and removes a small real evidence-only fixture beside
the retained evidence, proving the exact package `drvPath` is unchanged while
preserving the file-scoped input closure. Focused Task 2 tests: 8/8; Task 1
schema-v3 checker tests: 59/59; `nix flake check --no-build` passed.

The authentic package and its frontier remain unchanged: blocked,
`math.floor` 1376 at 422:18, `arith.negf` 1369, `math.absi` 1156, and
`calyx_authorized: false`; no backend action ran.

## Fix round 2: regression-fixture validity

Relocated bundle fixtures now rewrite their command claims from independently
resolved flake authority and first pass `verify_output`.  The prepared-output
replacement then reaches and asserts `preparation replay mismatch`; the
manifest-selected stub checker reaches and asserts `manifest command vector
mismatch`, rather than failing only because copied commands name the original
bundle path.

The derivation-sensitivity proof now changes the tracked, tiny excluded
`semantic-size1-pass-only/stdout.bin` only in a detached `/dev/shm` Git
worktree.  Its exact package `drvPath` was identical before and after the byte
mutation, and the live worktree bytes were checked unchanged after removal.
Focused Task 2 tests passed 8/8 with these baseline and precise-error checks.
