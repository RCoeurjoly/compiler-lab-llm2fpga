# Exact TinyStories f64-floor successor frontier

Task 2 rotates the registered exact normalized package to Task 1's reviewed
plugin, without changing the c22 input, normalized artifact, MLIR parser,
schema-v3 checker, model identity, or either pipeline identity.

## Authenticated identities

- reviewed plugin: `ec7aa6d4ad5f33696e9599ad23390209bb705cbea78af6ea759daba8d7c767ac`
- fixed c22 input: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- fixed normalized artifact: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- replayed prepared artifact: `fcbad9bd41c535c278abb617e8f6d5de89209cb0818a1a6341c7e98b211ebf3e`
- legality file: `d17e80b7a40d415eb0cb905c3e9afbdabad8463aa668d603657390e46bfc1614`
- legality receipt self-hash: `070f5f67e7469ad4f7d515115e707400e308d411e8b5fb08c8c79bfb383fbca4`
- manifest: `1ea899fd1ddb2e1d2d898327b3241012aa63e8ea90fde9cd04af78fb2b80ce86`

The independent verifier resolved the Nix authority, replayed normalization
and preparation under `/dev/shm`, byte-compared both replayed artifacts, and
replayed the schema-v3 checker. The receipt is consequently bound to the
measured prepared bytes rather than to a manifest claim.

## Successor classification

The replayed legality receipt reports zero `math.floor` operations. It remains
`blocked`, with `calyx_authorized: false`, because the following measured
prohibited classes remain:

| Operation | Count | First original-text location |
| --- | ---: | --- |
| `arith.negf` | 1,369 | line 464, column 18 |
| `math.absi` | 1,156 | line 855, column 16 |

The earliest successor is therefore `arith.negf` at line 464, column 18. A
follow-up plan may target only that operation and its exact semantic context;
it must not assume these counts or locations without a fresh replay.

## Scope boundary

This task ran the registered pre-Calyx build, independent verifier, and
registration tests only. It did not invoke CIRCT, Calyx, SystemVerilog,
synthesis, or board tooling. Residual legality keeps full-model Calyx lowering
unauthorized.
