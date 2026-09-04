# Exact TinyStories-1M strided unit-collapse extension evaluation

The rebuilt pass was replayed in causal order against the authenticated
offset-zero, offset-seven, and collapsed-copy affine probes, and only then the
18,933,168-byte retained c22 flat-SCF artifact. No Calyx stage ran and no Nix
pipeline stage was registered.

## Decision

`valid_normalized_output`

- Normalized artifact: `artifacts/comparison/tinystories-1m-exact-unit-collapse-extension-evidence/complete-retained-c22-flat-scf/output.mlir`
- Earliest residual pair: `memref.copy` with 2 defining boundary operations,
  `305f808006699f16a90f0ba99bfd4e7539e9587c91f70a3916b5d177ee34dd82`.

## Semantic probes

| Probe | Status | Complete affine mapping |
| --- | --- | --- |
| `semantic-offset-zero` | `proven` | `source: O=0, S=[64] ; target: O=0, S=[64]` |
| `semantic-offset-seven` | `proven` | `source: O=7, S=[64] ; target: O=7, S=[64]` |
| `semantic-collapsed-copy` | `proven` | `source: O=7, S=[64] ; target: O=0, S=[64]` |

## Full registered-blocker census

| Registered class | Before | After |
| --- | ---: | ---: |
| `memref.collapse_shape` | 4,682 | 0 |
| `memref.copy` | 3,228 | 1,022 |
| `memref.expand_shape` | 921 | 0 |
| `memref.reinterpret_cast` | 11,449 | 0 |

- Full output parseable: `true`
- New invalid classes: `0`
- Complete operation-name census: pinned `mlir-opt -mlir-print-op-generic`,
  deterministically recomputed by the independent verifier
- Registered blocker total after: `1,022` (only the four tabled
  collapse/copy/expand/reinterpret classes)
- Additional unregistered residual `memref.subview` operations: `0`
- Next causal pair: derived from the earliest residual registered blocker and
  its defining chain, never from class frequency. Both operands terminate
  directly at static `memref.alloc` boundaries; there is no intermediate view
  in this earliest chain.
- Semantic boundary/access status: `proven`
- Input SHA-256: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- Tool SHA-256: `3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`
- Predecessor plugin SHA-256: `6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9`
- Rebuilt plugin SHA-256: `9a96615321f61f04d250cb2cf872f1fedc317cb4555c9cece457d0bbe842e984`
- Exact pipeline: `builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`
- Measured time over four ordered executions: `2552310605` ns
