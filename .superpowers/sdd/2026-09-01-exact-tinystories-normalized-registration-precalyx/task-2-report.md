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
