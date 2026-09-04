# Exact TinyStories-1M static subview extension

## Scope and decision

`llm2fpga-lower-static-memref-views-for-calyx` now composes a fully static,
non-rank-reducing `memref.subview` into the existing recursive
`StaticMemRefView` model. The accepted result must have the exact static shape,
strides, and offset implied by its source view. Existing load, store, and copy
rewrites consume the composed view, and view operations are erased only after
their uses are gone.

This is only the Task 2 pass extension. It does not replay the complete retained
c22 flat-SCF artifact, register a Nix pipeline stage, or invoke Calyx.

## Root cause and RED

The pass flattened a ranked static function argument before it inspected
`memref.subview`. Because `getStaticView` had no subview case, access rewrites
could not consume the view and cleanup did not erase it. The verifier therefore
saw the original two-dimensional offsets on a newly one-dimensional source:

```text
error: expected 1 offset values, got 2
note: ... (memref<4096xi64>) -> memref<64x1xi64, strided<[64, 1]>>
```

The failure was reproduced directly with the authenticated baseline plugin
before production edits:

- plugin:
  `/nix/store/p01jw41h2jm2pr8xxww3acrjgx5rl1qn-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`;
- plugin SHA-256:
  `6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744`;
- `mlir-opt` SHA-256:
  `3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`;
- exact Task 3 reproducer exit: `1` with the diagnostic above;
- initial behavioral suite: five expected feature/safety failures and one
  fail-closed layout-verifier control;
- focused copy regression against the baseline: exit `1` at the same changed
  argument rank.

## Narrow implementation

For a `memref::SubViewOp`, `getStaticView` now requires all of the following:

- the source resolves recursively to a `StaticMemRefView`;
- offsets, sizes, and strides are fully static;
- source-view rank equals result rank;
- result shape equals the static sizes;
- the result layout is fully static and equals
  `sourceOffset + sum(offset[d] * sourceStride[d])` with strides
  `sourceStride[d] * subviewStride[d]`.

Before mutating function argument types, the pass checks every live subview and
its transitive view users. If the view is unsupported or cannot be eliminated
through the existing load/store/copy rewrites, its originating argument is not
flattened. Protection is computed to a fixpoint against the remaining final
candidate map. Thus a copy whose other root becomes protected also protects
every root whose supported view would otherwise survive. The actual rewrites
consume that same final map. Cleanup uses reverse use order and erases only
use-empty view operations.

Recursive `memref.reinterpret_cast` handling resolves the underlying base and
uses the reinterpret operation's own offset and strides as absolute metadata;
it does not add a source-view offset. Subview offset multiplication/addition
and stride multiplication use checked signed arithmetic. Overflow returns no
view and therefore protects the originating argument.

## Exact post-pass affine proof

The test reads generic post-pass IR, reconstructs the complete arithmetic DAG,
rejects non-affine multiplication, and compares literal offsets, coefficients,
variable domains, base argument identities, and memory roles. It does not use a
sample point.

| Case | Domain | Emitted linear index | Base and roles |
| --- | --- | --- | --- |
| exact identity/offset | `i0 in [0,64)`, `i1 in [0,1)` | `0 + 64*i0 + 1*i1` | flattened argument 0; store target and load source |
| nonzero offset/stride | `i0 in [0,16)`, `i1 in [0,8)` | `64 + 128*i0 + 2*i1` | flattened argument 0; store target and load source |
| subview to rank-two reinterpret | `i in [0,2)`, `j in [0,2)` | `0 + 2*i + 1*j` | flattened argument 0; reinterpret offset is absolute |
| subview/collapse to rank-one reinterpret | `i in [0,4)` | `0 + 2*i` | flattened argument 0; no intermediate view base survives |

The exact emitted bodies are structurally:

```mlir
// Exact case.
%c64 = arith.constant 64 : index
%0 = arith.muli %arg1, %c64 : index
%1 = arith.addi %0, %arg2 : index
memref.store %arg3, %arg0[%1] : memref<4096xi64>
%2 = memref.load %arg0[%1] : memref<4096xi64>
```

```mlir
// Nonzero composition case.
%c2 = arith.constant 2 : index
%c64 = arith.constant 64 : index
%c128 = arith.constant 128 : index
%0 = arith.muli %arg1, %c128 : index
%1 = arith.addi %0, %c64 : index
%2 = arith.muli %arg2, %c2 : index
%3 = arith.addi %1, %2 : index
memref.store %arg3, %arg0[%3] : memref<4096xi64>
%4 = memref.load %arg0[%3] : memref<4096xi64>
```

Both outputs parse and contain no `memref.subview`. The exact Task 3
one-operation reproducer also parses and reduces to a function over
`memref<4096xi64>` with only `return`. A static subview-to-subview copy contains
no `memref.subview` or `memref.copy` after the pass; it becomes a two-dimensional
`scf.for` nest with flattened load/store accesses.

## Unsupported behavior

Unsupported cases are never reported as legalized:

- a live rank-reducing subview remains explicit, its source argument remains
  `memref<64x64xi64>`, and the output parses;
- a live dynamic-offset subview remains explicit, its source argument remains
  `memref<64x64xi64>`, and the output parses;
- a rank-reducing subview followed by a reinterpret stays explicit with its
  original rank-two root;
- a supported A/B copy paired with a live dynamic unsupported sibling on B
  leaves both roots and all views explicit, in both copy directions and both
  subview enumeration orders;
- offset multiplication, offset addition, or stride multiplication overflow
  leaves the reinterpret/subview chain explicit and the root unflattened;
- a result layout inconsistent with the statically inferred subview layout is
  rejected by the MLIR verifier with `mismatch of result layout` and produces
  no output;
- dynamic size/stride sentinels, non-static result layouts, unresolved source
  views, and mismatched static shapes/layouts return no `StaticMemRefView` and
  therefore cannot be claimed by this extension.

## GREEN and plugin identity

The plan named `nix build .#mlir-passes -L`, but this flake has no such output.
Its single requested derivation is exposed as `.#llm2fpgaMlirPasses`; only that
plugin derivation was built.

- build: `nix build .#llm2fpgaMlirPasses -L` — PASS;
- focused suite:
  `nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_subview_extension.py -v`
  — `Ran 15 tests`, `OK`;
- output:
  `/nix/store/jpbaq3vd25spvvrb90gj5hb3k5ysp3h3-llm2fpga-mlir-passes-0.1.0`;
- plugin bytes: `21,720,848`;
- plugin SHA-256:
  `6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9`;
- the new plugin digest differs from the authenticated baseline digest.

## Residual risks

- The complete 18,933,168-byte retained c22 artifact is Task 3 scope, so this
  task does not claim a later compiler frontier or a valid normalized full
  output.
- View kinds outside the existing reinterpret/expand/collapse/subview model
  remain unsupported and explicit.
