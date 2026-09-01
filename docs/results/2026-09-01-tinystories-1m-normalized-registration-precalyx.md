# Exact TinyStories normalized registration, pre-Calyx only

The registered package is `tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.
It accepts only the file-scoped immutable c22 input, reviewed MLIR pass plugin,
pinned MLIR parser, and materialized schema-v3 legality checker. It does not
invoke CIRCT, Calyx, SystemVerilog export, synthesis, or board work.

## Reproduction and identities

`nix build --no-link --print-out-paths
.#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L` produced
`/nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.

- c22 input: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- pass plugin: `901fd383935d5af48e616eb881ae1b72408f4cb26dfbef94ea7be3049d61760f`
- normalized `flat.scf.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- prepared `pre-calyx.mlir`: `54a7df3fec336c5418d3562441a3f9affe45702eb107b89092bc2f7b53afca31`
- legality file / receipt self-hash: `e7cc29335cb83efc22833ec818d1e7ed56235393bbcbb42a822a3402134c6de0` / `451628dba61ea805b09007e89b2135d00dcd93cf225ed4d6d9625a05a598de30`
- manifest: `93f77dbc196dee1c9a04a860cf5242e79497436b09af497a5dd4b4efd7b0fd6e`

The normalization pipeline is
`builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`.
The no-scout preparation pipeline contains exactly one
`llm2fpga-lower-negf-for-calyx`, immediately after exact-math and before
i1-uitofp. Both artifacts parse.
The four registered raw memref blocker counts are zero.

## Legality frontier

The schema-v3 receipt has verified parser identity and status `ok`, so
`calyx_authorized` is true. The independently replayed preparation contains
zero `math.floor`, zero `arith.negf`, and zero `math.absi` operations. Its
complete scanner census and diagnostics are empty; therefore there is no
first residual location. This authenticates eligibility for a separately
planned full-model Calyx lowering only.

## Test evidence

The initial RED failed because the registered derivation still carried the
previous plugin authority. GREEN evidence is the package build, independent
checker replay, and the registration/no-Calyx suite. Mutation coverage rejects
stale c22, plugin, normalized, and prepared hashes; a false legality status;
an i64 `math.absi` residual; and omitted, duplicated, or reordered NegF
preparation pipelines. The derivation-input test confirms that the full
evidence directory is not an input source.

The verifier independently resolves the c22 input, reviewed plugin, pinned
parser, exact MLIR commands, tracked checker source, and Nix-materialized
checker; manifest values are only claims checked against that authority. It
replays normalization and preparation into `/dev/shm` and byte-compares both
artifacts before accepting the legality receipt. Coherent parser-clean and
checker-stub temporary-bundle attacks are rejected.

No Calyx or downstream hardware action was invoked. A later plan may use the
clean authorization record as its starting point.
