# Exact TinyStories i64 `math.absi` successor result

Task 1 commit `558a503` supplied the reviewed pass plugin. Its measured
`LLM2FPGAMLIRPasses.so` SHA-256 is
`901fd383935d5af48e616eb881ae1b72408f4cb26dfbef94ea7be3049d61760f`.
Only that measured plugin authority was rotated; the c22 input, normalized
artifact, parser, checker, model, normalization pipeline, and preparation
pipeline are unchanged.

## Rebuilt authenticated bundle

`nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L` produced
`/nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`.

- c22 input: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- plugin: `901fd383935d5af48e616eb881ae1b72408f4cb26dfbef94ea7be3049d61760f`
- normalized `flat.scf.mlir`: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`
- prepared `pre-calyx.mlir`: `54a7df3fec336c5418d3562441a3f9affe45702eb107b89092bc2f7b53afca31`
- legality file: `e7cc29335cb83efc22833ec818d1e7ed56235393bbcbb42a822a3402134c6de0`
- receipt self-hash: `451628dba61ea805b09007e89b2135d00dcd93cf225ed4d6d9625a05a598de30`
- manifest: `93f77dbc196dee1c9a04a860cf5242e79497436b09af497a5dd4b4efd7b0fd6e`

The independently replayed schema-v3 legality receipt reports `status: ok`,
`prohibited_ops: {}`, `scanner_diagnostics: []`, and no first locations.
The carried `math.floor`, `arith.negf`, and `math.absi` counts are all zero.
`calyx_authorized` is therefore `true`.

## Complete generic prepared-operation census

The pinned parser independently printed the prepared MLIR in generic form.
The complete operation census was:

| Operation | Count |
| --- | ---: |
| `arith.addi` | 36,720 |
| `arith.andi` | 115 |
| `arith.bitcast` | 2,738 |
| `arith.cmpf` | 1,376 |
| `arith.cmpi` | 6,693 |
| `arith.constant` | 309 |
| `arith.divf` | 1,376 |
| `arith.extui` | 214 |
| `arith.fptosi` | 2,745 |
| `arith.index_cast` | 917 |
| `arith.muli` | 28,169 |
| `arith.remsi` | 107 |
| `arith.select` | 7,959 |
| `arith.shli` | 106 |
| `arith.shrsi` | 2,229 |
| `arith.sitofp` | 5,497 |
| `arith.subi` | 2,434 |
| `arith.xori` | 2,525 |
| `builtin.module` | 1 |
| `func.func` | 1 |
| `func.return` | 1 |
| `memref.alloc` | 13,033 |
| `memref.get_global` | 31 |
| `memref.global` | 31 |
| `memref.load` | 59,553 |
| `memref.store` | 33,973 |
| `scf.for` | 42,558 |
| `scf.yield` | 42,558 |

No backend command occurs in the registered closure. No full-model Calyx,
SV, synthesis, or board operation was invoked. This clean receipt authorizes
only a separately planned full-model Calyx lowering frontier.
