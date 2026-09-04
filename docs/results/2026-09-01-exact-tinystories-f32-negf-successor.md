# Exact TinyStories f32 NegF successor, pre-Calyx only

The shared and exact preparation contracts now run
`llm2fpga-lower-negf-for-calyx` exactly once, immediately after
`llm2fpga-lower-exact-math-for-calyx` and before i1-uitofp. The shared route
retains its explicitly opt-in scout suffix after NegF.

## Authenticated identities

- plugin: `da138b78750abcdcc7f5f467d0991b1e2eb9cf04708186a6b4f0dd8e14df2c6e`
- normalized `flat.scf.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- prepared `pre-calyx.mlir`: `eae93f4797d63601fbbd24a58e619a41085025a79b864b53cf4eba9b6f6e8d46`
- legality file: `6ee2f3266c7d51f9e461a0a6d3dfc35deefe4f8dae941cfefa925618b8005de0`
- legality receipt self-hash: `1a1939baef38f56aa0c8e88762b9b6c6e4c77f15078e5436e1fa5fccfaac3f82`
- manifest: `38235f4195db8d47f74e5f4de12492d79545d44705018e90674410149dc415b9`

The c22, normalization, parser, checker, model, and normalization identities
remain unchanged. The registered package only runs MLIR normalization,
preparation, parsing, and the legality checker; its recorded command vector
contains no CIRCT, Calyx, SV, synthesis, or board command.

## Successor frontier

The independently replayed receipt is `blocked`, with
`calyx_authorized: false`, no scanner diagnostics, and zero `math.floor` and
`arith.negf` operations. The only measured prohibited successor is
`math.absi`: 1,156 operations, first occurring in the original prepared text
at line 864, column 16.

The next plan may target only that measured `math.absi` frontier. This task
does not run a full-model Calyx, SV, synthesis, or board route.
