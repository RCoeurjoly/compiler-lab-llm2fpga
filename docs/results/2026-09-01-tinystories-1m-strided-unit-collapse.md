# Exact TinyStories-1M strided unit-collapse extension

## Scope and decision

`llm2fpga-lower-static-memref-views-for-calyx` now resolves one additional
static `memref.collapse_shape` family through the recursive
`StaticMemRefView` model:

```text
shape [N, 1], strides [S, 1], offset O, reassociation [[0, 1]]
  -> shape [N], stride [S], offset O
```

`N` and `S` must both be positive. The result shape, static offset, and static
stride must equal the values above exactly. Existing load, store, and copy
rewrites consume the returned underlying base and materialize the complete map
`O + S*i`.

This is only the bounded Task 1 pass extension. It does not replay the full
retained c22 artifact, change a Nix stage, invoke Calyx, or alter model/runtime
behavior.

## Root cause and RED

The reviewed collapse branch accepted a source view only when its strides
equaled the identity strides computed from its shape. For shape `[64,1]`, the
identity stride vector is `[1,1]`, so the authenticated subview result with
strides `[64,1]` returned no view even though the unit trailing dimension makes
the collapse exactly representable. The dependency preflight then correctly
kept the root ranked, leaving the complete subview/collapse chain explicit.

The reviewed plugin was:

- path:
  `/nix/store/jpbaq3vd25spvvrb90gj5hb3k5ysp3h3-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`;
- bytes: `21,720,848`;
- SHA-256:
  `6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9`.

After correcting one negative assertion before any C++ edit, the 12-test RED
had exactly three expected failures: offset zero, offset seven, and the
collapsed-copy chain. The reviewed plugin emitted the original ranked roots,
subviews, collapses, and copy in all three cases. The other nine identity and
fail-closed controls passed.

The finalized suite was also forced against that exact reviewed plugin after
implementation and reproduced the same three failures.

## Review round 1: direct-root safety

Review found a separate preflight defect exposed by the new supported chain.
The old dependency proof walked from collected subview results, so it proved
only uses below those subviews. A direct rank-sensitive sibling of the root was
not visited. With a direct `memref.dim %source, 0`, the initial Task 1 plugin
flattened `memref<64x64xi64>` to `memref<4096xi64>` and canonicalized the
observable dimension from 64 to 4096. Direct typed-call and return-escape
controls instead failed verification after receiving the changed argument
type.

Strict fix-round RED used the initial Task 1 plugin and ran 18 tests with
exactly four failures: direct `memref.dim`, direct typed call, direct return,
and a two-root collapsed-copy dependency whose target had the direct
`memref.dim`. A transitive typed call was already protected by the recursive
proof, while direct loads/stores remained rewriteable; those two controls were
green and distinguish the missing root seed from the already-correct recursive
and access-rewrite behavior.

## Narrow implementation

The identity-layout collapse path is unchanged and remains first. The new
second path requires all of the following before returning a view:

- source-view shape is exactly rank two `[N,1]`, with `N > 0`;
- source-view strides are exactly `[S,1]`, with `S > 0`;
- reassociation is exactly one group containing dimensions `[0,1]`;
- result is static rank one with shape `[N]`;
- result layout exposes one static stride equal to `S` and a static offset
  equal to the source-view offset `O`.

Anything else returns `std::nullopt`. No result type is changed in place. The
underlying base, offset, and already checked subview composition are reused, so
the dependency-fixpoint preflight and reverse dead-view cleanup remain the only
argument-mutation and erasure gates.

The fix-round preflight now seeds `canRewriteAllViewUses` from every candidate
root argument against the current complete candidate map. Any direct or
transitive unhandled use removes that root from the map, and the existing loop
repeats until no additional root becomes protected. Loads, stores, and fully
resolvable view/copy chains stay rewriteable. `memref.dim`, typed calls,
returns/escapes, and unknown users protect the root. Batch removal preserves
order-independent convergence when a protected root invalidates a copy peer.

## Complete affine proofs

The tests run the real plugin, parse its generic output with the pinned
`mlir-opt`, independently reconstruct every index constant/add/multiply node,
reject non-affine multiplication, and compare literal base identities, memory
roles, domains, offsets, and coefficients.

| Case | Domain | Exact post-pass map | Base and roles |
| --- | --- | --- | --- |
| offset zero | `i in [0,64)` | `0 + 64*i` | flattened argument 0; store target and load source |
| offset seven | `i in [0,64)` | `7 + 64*i` | flattened argument 0; store target and load source |

Both outputs parse, contain `memref<4096xi64>`, and contain no
`memref.subview` or `memref.collapse_shape`.

The collapsed-copy proof lowers two supported chains to one `scf.for` over
`i in [0,64)`. It reconstructs the source load as base argument 0 with
`7 + 64*i`, and the target store as base argument 1 with `0 + 64*i`. The
output has neither view operation nor `memref.copy`.

## Unsupported and preserved behavior

- A trailing dimension of 2 is rejected by the MLIR input verifier as a
  non-contiguous collapse; no output is accepted.
- A wrong result stride is rejected before the pass with the expected type
  `memref<64xi64, strided<[64]>>`.
- A wrong result offset is rejected before the pass with the expected offset-7
  result type.
- Dynamic subview/result offset metadata remains explicit with its
  `memref<64x64xi64>` root.
- A rank-three source and reassociation `[[0],[1,2]]` remain explicit with the
  `memref<4x64x64xi64>` root.
- A zero leading extent remains explicit with its `memref<8x8xi64>` root.
- A zero leading stride remains an explicit reinterpret/collapse over the
  ranked root; canonicalization may remove only the preceding identity
  subview.
- A supported collapse sharing a root with a live dynamic unsupported sibling
  remains explicit together with that sibling; the root stays rank two.
- A direct `memref.dim` sibling retains the rank-two root, explicit supported
  chain, and dimension 64; it never observes 4096.
- Direct typed calls and returned/escaped roots retain their original ranked
  types and explicit chains. A typed call below the collapse is protected by
  the same recursive traversal.
- Direct loads/stores are still rewritten safely. Their exact maps are
  `64*i+j` for the direct access and `64*i` through the supported collapse.
- Protection propagates across a collapsed-copy dependency: a direct
  rank-sensitive target user protects both target and source roots, leaving
  both chains and `memref.copy` explicit.
- The pre-existing identity-layout collapse control still lowers exactly.
- The prior 15-test subview suite retains recursive absolute reinterpret
  semantics, copy-protection fixpoint behavior in both directions/orders,
  reverse cleanup, and all three checked-overflow protections.

## GREEN and plugin identity

- build: `nix build .#llm2fpgaMlirPasses -L` — exit 0;
- focused suite: 18 tests — `OK`;
- prescribed combined collapse/subview suite: 33 tests — `OK`;
- three relevant static-memref/pass integration assertions — `OK`;
- output:
  `/nix/store/56y2lxxivg9aalx8hn82cwymdgqmhq3n-llm2fpga-mlir-passes-0.1.0`;
- plugin bytes: `21,720,080`;
- plugin SHA-256:
  `81d0c95cdbcc852f347b6cebb80d65da359cbbc488b4af2b829f1eb8125a87d0`.

The fix-round digest differs from both the reviewed predecessor and initial
Task 1 plugin digests.

## Residual risks and non-claims

- Arbitrary strided collapses, other reassociations, non-unit trailing
  dimensions, dynamic metadata, nonpositive extents/strides, and higher-rank
  changes remain unsupported.
- Result offset/stride mismatch is statically rejected by the current MLIR
  verifier; the pass independently checks those fields but does not claim a
  post-parser adversarial mismatch surface.
- Unknown direct/transitive root users conservatively retain the ranked root;
  supporting another safe user requires an explicit rewrite and proof.
- Full-artifact replay and selection of the next compiler frontier remain Task
  2 scope. No claim is made about new full-artifact blocker counts or Calyx
  eligibility.
