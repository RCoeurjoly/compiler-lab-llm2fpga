# TinyStories-1M softmax lowering diagnosis

## Finding

The authenticated package-aware graph does not lose the softmax computation at
`flatten-memref`.  The semantic names have already been erased by the
`torch-mlir` backend-to-Linalg conversion and the subsequent Linalg-to-loops
conversion.  The SCF artifact itself contains the complete computation, but
represents reductions as memory-carried loops rather than `scf.for
iter_args`.

For each head, row-max is represented as:

1. an initialized `alloc` buffer;
2. loads of the score and the current max inside three nested loops;
3. `arith.cmpf ugt` and `arith.select` operations; and
4. a store of the selected max back to that same buffer.

The stabilized subtraction then loads the score and that max buffer.  The
exponential, sum, and division are separate loops.  There is no
`arith.maximumf`, no `scf.for ... iter_args`, and no source-level role name in
this representation.

## Evidence

The exact package-aware stage artifacts are:

| stage | SHA-256 | bytes |
|---|---|---:|
| Linalg | `82119011db5f0296701b088f728b1e7c18de8210af69b5ec5bfc96be4c1b5354` | 29,142,081 |
| SCF | `98dc99264388ad836b98fade83c71abb4d194a6840371e26cdb98465916c0c33` | 29,221,149 |
| flat SCF | `52382658fed8629d5e6757c6e9d7cb400d30dc1e05453c371c23d8ea8785ab9c` | 29,375,724 |

In SCF, the row-max loop contains `arith.cmpf ugt` followed by two
`arith.select` operations and stores to the max buffer.  In flat SCF the same
chain remains, while shaped memrefs become one-dimensional memrefs and affine
indices are made explicit.  The first real-graph bridge failure at the flat
SCF `arith.subf` is therefore a missing provenance binding, not evidence that
the subtraction or max computation is absent.

## Consequence

The bridge must not require an `iter_args`/`maximumf` shape as the only valid
reduction encoding.  The safe compiler-side direction is to preserve a
softmax provenance manifest (or operation attributes) before lowering, binding
each head's score, max, delta, exponential, sum, normalization, causal mask,
and output buffers to exact SSA/memref/index identities.  The manifest must be
authenticated against the stage hashes and must not replace structural checks
on the lowered graph.

Until that metadata-preserving boundary exists, the real graph remains
fail-closed.  No custom softmax op, RTL, timing, or hardware inference claim
is justified by the current lowering artifacts.
