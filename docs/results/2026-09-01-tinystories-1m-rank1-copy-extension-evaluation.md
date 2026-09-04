# Exact TinyStories-1M direct rank-one copy extension evaluation

The size-1 and size-64 live copy probes were replayed first at the pass boundary and through the exact integrated normalization pipeline. Only after both semantic proofs succeeded was the immutable 18,933,168-byte c22 artifact replayed. No Nix stage was registered and no Calyx command ran.

## Decision

- `zero_registered_blockers: true`
- Decision: `zero_registered_blockers`
- Exact normalized artifact: `artifacts/comparison/tinystories-1m-exact-rank1-copy-extension-evidence/complete-retained-c22-flat-scf/output.mlir`
- Artifact SHA-256: `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`

## Semantic probes

| Probe | Status | Loop domain | Direction/index | Live observation |
| --- | --- | --- | --- | --- |
| `size1` | `proven` | `[0,1)` | source alloc 0 -> target alloc 1 at `i` | live index 0 |
| `size64` | `proven` | `[0,64)` | source alloc 0 -> target alloc 1 at `i` | live index 63 |

## Complete registered blocker census

| Registered class | Before | After |
| --- | ---: | ---: |
| `memref.collapse_shape` | 4,682 | 0 |
| `memref.copy` | 3,228 | 0 |
| `memref.expand_shape` | 921 | 0 |
| `memref.reinterpret_cast` | 11,449 | 0 |

- Pass exit: `0`
- Parse exit: `0`
- After-only operation classes: `0`
- Complete input/output generic operation censuses are retained and independently replayable.

## Handoff boundary

The exact artifact is bound for a separate stage-registration and pre-Calyx legality plan. This task authorizes neither action and did not invoke Calyx.
