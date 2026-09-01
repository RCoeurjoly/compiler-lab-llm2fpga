# Exact TinyStories normalized registration, pre-Calyx only

The registered package is `tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.
It accepts only the file-scoped immutable c22 input, reviewed MLIR pass plugin,
pinned MLIR parser, and materialized schema-v3 legality checker. It does not
invoke CIRCT, Calyx, SystemVerilog export, synthesis, or board work.

## Reproduction and identities

`nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L` produced
`/nix/store/z988ixk8rjq1cm5mbf1351lz2ny332cv-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.

- c22 input: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- pass plugin: `ec7aa6d4ad5f33696e9599ad23390209bb705cbea78af6ea759daba8d7c767ac`
- normalized `flat.scf.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- prepared `pre-calyx.mlir`: `fcbad9bd41c535c278abb617e8f6d5de89209cb0818a1a6341c7e98b211ebf3e`
- legality file / receipt self-hash: `d17e80b7a40d415eb0cb905c3e9afbdabad8463aa668d603657390e46bfc1614` / `070f5f67e7469ad4f7d515115e707400e308d411e8b5fb08c8c79bfb383fbca4`
- manifest: `1ea899fd1ddb2e1d2d898327b3241012aa63e8ea90fde9cd04af78fb2b80ce86`

The normalization pipeline is
`builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`.
The no-scout preparation pipeline is the existing sequence through
`llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse`. Both artifacts parse.
The four registered raw memref blocker counts are zero.

## Legality frontier

The schema-v3 receipt has verified parser identity and status `blocked`, so
`calyx_authorized` is false. The independently replayed preparation contains
zero `math.floor` operations. The measured successor frontier is `arith.negf`:
1,369 at line 464, column 18; the next remaining class is `math.absi`: 1,156
at line 855, column 16. Those residuals are deliberately not lowered here.

## Test evidence

The initial RED failed because the registered derivation still expected the
old plugin identity `79c0ab...d738`. GREEN evidence is the package build,
independent checker replay, and the registration/no-Calyx suite. Mutation
coverage rejects stale c22, plugin, and normalized hashes; a false legality
status; and an altered preparation pipeline. The derivation-input test confirms
that the full evidence directory is not an input source.

The verifier independently resolves the c22 input, reviewed plugin, pinned
parser, exact MLIR commands, tracked checker source, and Nix-materialized
checker; manifest values are only claims checked against that authority. It
replays normalization and preparation into `/dev/shm` and byte-compares both
artifacts before accepting the legality receipt. Coherent parser-clean and
checker-stub temporary-bundle attacks are rejected.

No Calyx or downstream hardware action is implied. A later plan may address
only the measured `arith.negf` successor frontier.
