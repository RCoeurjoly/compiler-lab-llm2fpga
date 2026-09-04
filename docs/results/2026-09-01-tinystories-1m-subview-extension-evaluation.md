# Exact TinyStories-1M static-subview extension evaluation

The rebuilt pass was replayed in causal order against the authenticated
predecessor reproducer, the two complete affine probes, and only then the
18,933,168-byte retained c22 flat-SCF artifact. No Calyx stage ran and no Nix
pipeline stage was registered.

## Decision

`valid_normalized_output`

- Normalized artifact: `artifacts/comparison/tinystories-1m-exact-subview-extension-evidence/complete-retained-c22-flat-scf/output.mlir`

## Semantic probes

| Probe | Status | Complete affine mapping |
| --- | --- | --- |
| `semantic-identity-offset` | `proven` | `offset=0, coefficients=[64, 1]` |
| `semantic-nonzero-offset-stride` | `proven` | `offset=64, coefficients=[128, 2]` |

## Full registered-blocker census

| Registered class | Before | After |
| --- | ---: | ---: |
| `memref.collapse_shape` | 4,682 | 4,672 |
| `memref.copy` | 3,228 | 1,022 |
| `memref.expand_shape` | 921 | 0 |
| `memref.reinterpret_cast` | 11,449 | 1 |

- Full output parseable: `true`
- New invalid classes: `0`
- Complete operation-name census: pinned `mlir-opt -mlir-print-op-generic`,
  deterministically recomputed by the independent verifier
- Registered blocker total after: `5,695` (only the four tabled
  collapse/copy/expand/reinterpret classes)
- Additional unregistered residual `memref.subview` operations: `4,672`
- Next causal pair: static strided `memref.collapse_shape` composition over an
  already-supported `memref.subview`
- Semantic boundary/access status: `proven`
- Input SHA-256: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- Tool SHA-256: `3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`
- Baseline plugin SHA-256: `6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744`
- Rebuilt plugin SHA-256: `6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9`
- Exact pipeline: `builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`
- Measured time over four ordered executions: `2831686583` ns
