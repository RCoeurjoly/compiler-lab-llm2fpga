# Exact TinyStories normalized registration, pre-Calyx only

The registered package is `tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.
It accepts only the file-scoped immutable c22 input, reviewed MLIR pass plugin,
pinned MLIR parser, and materialized schema-v3 legality checker. It does not
invoke CIRCT, Calyx, SystemVerilog export, synthesis, or board work.

## Reproduction and identities

`nix build --no-link --print-out-paths
.#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L` produced
`/nix/store/y4w97n0x4vvq8s1w8kldix1663w9iffa-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.

- c22 input: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- pass plugin: `da138b78750abcdcc7f5f467d0991b1e2eb9cf04708186a6b4f0dd8e14df2c6e`
- normalized `flat.scf.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- prepared `pre-calyx.mlir`: `eae93f4797d63601fbbd24a58e619a41085025a79b864b53cf4eba9b6f6e8d46`
- legality file / receipt self-hash: `6ee2f3266c7d51f9e461a0a6d3dfc35deefe4f8dae941cfefa925618b8005de0` / `1a1939baef38f56aa0c8e88762b9b6c6e4c77f15078e5436e1fa5fccfaac3f82`
- manifest: `38235f4195db8d47f74e5f4de12492d79545d44705018e90674410149dc415b9`

The normalization pipeline is
`builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`.
The no-scout preparation pipeline contains exactly one
`llm2fpga-lower-negf-for-calyx`, immediately after exact-math and before
i1-uitofp. Both artifacts parse.
The four registered raw memref blocker counts are zero.

## Legality frontier

The schema-v3 receipt has verified parser identity and status `blocked`, so
`calyx_authorized` is false. The independently replayed preparation contains
zero `math.floor` and zero `arith.negf` operations. The measured successor
frontier is `math.absi`: 1,156 at line 864, column 16. That residual is
deliberately not lowered here.

## Test evidence

The initial RED failed because the registered derivation still expected the
stale plugin identity `ec7aa6...67ac`. GREEN evidence is the package build,
independent checker replay, and the registration/no-Calyx suite. Mutation
coverage rejects stale c22, plugin, normalized, and prepared hashes; a false
legality status; and omitted, duplicated, or reordered NegF preparation
pipelines. The derivation-input test confirms that the full evidence directory
is not an input source.

The verifier independently resolves the c22 input, reviewed plugin, pinned
parser, exact MLIR commands, tracked checker source, and Nix-materialized
checker; manifest values are only claims checked against that authority. It
replays normalization and preparation into `/dev/shm` and byte-compares both
artifacts before accepting the legality receipt. Coherent parser-clean and
checker-stub temporary-bundle attacks are rejected.

No Calyx or downstream hardware action is implied. A later plan may address
only the measured `math.absi` successor frontier.
