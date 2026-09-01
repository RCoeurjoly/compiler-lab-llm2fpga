# Exact TinyStories normalized registration, pre-Calyx only

The registered package is `tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.
It accepts only the file-scoped immutable c22 input, reviewed MLIR pass plugin,
pinned MLIR parser, and materialized schema-v3 legality checker. It does not
invoke CIRCT, Calyx, SystemVerilog export, synthesis, or board work.

## Reproduction and identities

`nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L` produced
`/nix/store/azz64q7fcbbsqyja72mkryfdjkgqrvk4-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.

- c22 input: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- pass plugin: `79c0ab56022ce6c91279bca8aefeea7251a1eb19c92675f6df7b90265fb0d738`
- normalized `flat.scf.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- prepared `pre-calyx.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- legality file / receipt self-hash: `8c27b2419fd37434b360fd98b0fcdbc2b929767a9501f33ef05780c339c3e079` / `ad16079fd1fccf83d837507b526048dce4c87e0fa5744b9293e48bdd9d4a732c`

The normalization pipeline is
`builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`.
The no-scout preparation pipeline is the existing sequence through
`llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse`. Both artifacts parse.
The four registered raw memref blocker counts are zero.

## Legality frontier

The schema-v3 receipt has verified parser identity and status `blocked`, so
`calyx_authorized` is false. The earliest prohibited operation is `math.floor`
at line 422, column 18. Counts are `math.floor: 1376`, `arith.negf: 1369`,
and `math.absi: 1156`.

## Test evidence

The initial RED failed because the exact flake alias was absent. GREEN evidence
is the package build, independent checker replay, and five passing
registration/no-Calyx tests. Mutation coverage rejects stale c22, plugin, and
normalized hashes; a false legality status; and an altered preparation
pipeline. The derivation-input test confirms that the full evidence directory
is not an input source.

No Calyx or downstream hardware action is implied. A later plan may address
only the recorded `math.floor` frontier.
