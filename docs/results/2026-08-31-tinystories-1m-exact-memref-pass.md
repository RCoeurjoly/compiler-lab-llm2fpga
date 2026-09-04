# Exact TinyStories-1M static-memref-pass evaluation

The existing pass was evaluated without modifying it and without invoking
Calyx. All four authenticated representatives ran before the complete retained
c22 flat-SCF artifact. The protected current alias remains explicitly
unrealized; this experiment uses the retained authenticated c22 bytes.

## Decision

`compiler_pass_extension`

## Representatives

| Registered class | Classification | Remaining class count |
| --- | --- | ---: |
| `memref.collapse_shape` | `eliminated` | 0 |
| `memref.copy` | `preserved` | 1 |
| `memref.expand_shape` | `eliminated` | 0 |
| `memref.reinterpret_cast` | `eliminated` | 0 |

## Complete artifact census

| Registered class | Before | After |
| --- | ---: | ---: |
| `memref.collapse_shape` | 4,682 | unavailable |
| `memref.copy` | 3,228 | unavailable |
| `memref.expand_shape` | 921 | unavailable |
| `memref.reinterpret_cast` | 11,449 | unavailable |

- Input SHA-256: `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`
- Output SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Tool SHA-256: `3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`
- Plugin SHA-256: `6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744`
- Exact pipeline: `builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`
- Parseable output: `false`
- Unknown blocker classes: `0`
- New invalid signatures: `1`
- Full-artifact invariant status: `unavailable_due_invalid_output`
- Measured pass time over nine ordered executions: `1201333877` ns

## Earliest residual

`memref.subview` / `6149b92a9d179ef65caa53ff8dd33259b3d0c05085e5289384627b80c931f693`. The exact one-operation reproducer is `reproducers/tinystories-1m-exact-flat-scf-memref/task3-earliest-remaining/input.mlir`.

The public verifier closes the complete earliest-frontier claim. It requires
exact schemas for the inline signature, its memref descriptions, and the
source location; independently reconstructs the diagnostic-emitting operation
from the authenticated complete-run stderr and retained flat-SCF source; and
requires the claimed operation, signature, canonical signature digest,
classification, source location, and diagnostic to equal that reconstructed
`invalid[0]` frontier. The reproducer sidecar's operation, signature, digest,
and classification must equal the same object. Canonically rehashed unknown
keys, stale or rebound inline signatures, and sidecar disagreement are rejected.

This verification closure did not rewrite the canonical evaluation or
reproducer evidence. Their file SHA-256 identities remain
`26e0ddcaf0abc6100332378d2cacf0555f3560a7635bcdd60dbb9f47bd5ad0d8` and
`a93f7cf5e94cd7977c5dd038c023076a5594ea698386802d8dd9594cbcc8d5fe`,
respectively.

No Calyx stage ran and no pipeline stage was registered by this evaluation.
