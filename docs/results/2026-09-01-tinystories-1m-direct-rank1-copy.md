# Exact TinyStories-1M direct rank-one copy extension

## Scope and decision

`llm2fpga-lower-static-memref-views-for-calyx` now lowers one additional
`memref.copy` family:

```text
distinct memref.alloc source and target
  + equal positive static rank-one shape [N]
  + equal element type
  + static offset 0 and stride [1] on both operands
  -> for i in [0,N): target[i] = source[i]
```

The lowering reuses the existing `emitCopyLoopNest`; size one is not
special-cased. This is only the Task 1 pass extension. It does not replay the
full retained c22 artifact, register a Nix stage, invoke Calyx, or change
model/runtime behavior.

## Root cause and RED

`rewriteCopy` already resolved both direct rank-one allocations to equal
`StaticMemRefView` shapes, but then deliberately returned whenever both bases
were the original operands and both shapes had rank at most one. The reviewed
plugin therefore retained both live direct copies:

- `memref<1xi64>`;
- `memref<64xi64>`.

The finalized 12-test suite was forced against the reviewed plugin before the
C++ change. Ten semantic/safety controls passed and exactly the two supported
cases failed because `memref.copy` remained. The reviewed plugin identity was:

- path:
  `/nix/store/7nffqc9cn9da37py316ilmcarjpp9gbn-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`;
- bytes: `21,726,600`;
- SHA-256:
  `9a96615321f61f04d250cb2cf872f1fedc317cb4555c9cece457d0bbe842e984`.

## Narrow eligibility gate

The old early-return branch now continues into loop emission only when all of
the following are independently true:

- both resolved bases equal the original copy operands;
- both operands are defined by distinct `memref.alloc` operations;
- both types are static rank one with the same positive extent and element
  type;
- both resolved views have offset zero and one stride equal to one;
- extracting each concrete memref layout succeeds and independently yields
  static offset zero and stride one.

Any failed check retains the old return. The general recursive view-copy path,
argument/root protection, call and symbol handling, checked view arithmetic,
and cleanup ordering are unchanged. The copy is erased only after the common
loop emitter creates its load and store.

## Exact loop and direction proof

Both fixtures store a live function argument into the first allocation before
the copy and return a load from the second allocation after the copy. The test
parses generic pass-level IR, reconstructs the complete index arithmetic, and
compares literal loop bounds, allocation identity, memory role, offset, and
coefficient.

| Case | Loop domain | Source load | Target store | Live observation |
| --- | --- | --- | --- | --- |
| size 1 | `i in [0,1)`, step 1 | first alloc at `0 + 1*i` | second alloc at `0 + 1*i` | source initialized at 0; target loaded at 0 |
| size 64 | `i in [0,64)`, step 1 | first alloc at `0 + 1*i` | second alloc at `0 + 1*i` | source initialized at 63; target loaded at 63 |

Each pass-level output contains exactly one `scf.for`, one loop-carried source
load, one loop-carried target store, and no `memref.copy`. Both outputs parse.
The pass-level proof is intentional: the subsequent canonicalizer legally
folds the single-iteration size-one loop, while the pass itself must use the
same semantic loop implementation for both sizes.

## Unsupported and fail-closed behavior

The pass-only controls prove that these valid cases retain an explicit
`memref.copy` and introduce no `scf.for`:

- the same allocation is both source and target;
- equal dynamic rank-one allocations;
- rank-zero allocations;
- equal zero-extent rank-one allocations;
- equal rank-one allocations with static stride two;
- function-argument bases;
- global bases;
- a potentially aliasing cast view of the same allocation.

Static shape and element-type mismatches are rejected by the pinned MLIR
verifier before the pass because `memref.copy` requires equal shapes and equal
element types. No transformed output is accepted for either invalid input.

## GREEN and plugin identity

- build: `nix build .#llm2fpgaMlirPasses -L` — exit 0;
- focused suite: 12 tests — `OK`;
- prescribed direct/collapse/subview suite: 59 tests — `OK`;
- rebuilt output:
  `/nix/store/f6mglahvc3l9pnsanr0pgiww0wcsivgg-llm2fpga-mlir-passes-0.1.0`;
- rebuilt plugin bytes: `21,726,600`;
- rebuilt plugin SHA-256:
  `79c0ab56022ce6c91279bca8aefeea7251a1eb19c92675f6df7b90265fb0d738`.

The rebuilt digest differs from the reviewed predecessor digest.

## Residual risks and non-claims

- General view copies retain their already-reviewed behavior; this task does
  not generalize alias analysis.
- Dynamic shapes, rank zero, zero extents, non-unit/static layouts, non-alloc
  bases, and different valid type families remain unsupported.
- The full 18,933,168-byte c22 artifact and its 1,022 prior residual copies are
  Task 2 replay scope, so this task makes no new blocker-count, zero-blocker,
  stage-registration, or Calyx claim.
