# Task 2 implementer report: exact static subview memref extension

## Base and implementation head

- Assigned base: `edd4acb69beb9c7242722f323a96422fd40b8399`.
- Verified implementation head:
  `e61d08d78a8b4dbcabdd23d95efb1ec8ed442f6c`.
- Implementation commit: `fix: lower static subviews of flattened memrefs`.
- Worktree: `/home/roland/compiler-lab-llm2fpga/.worktrees/exact-tinystories-compiler`.
- Branch: `codex/exact-tinystories-compiler`.

No subagent was used. The implementation was confined to Task 2; no model,
runtime, Nix stage, Calyx, full-artifact evaluation, or pipeline registration
file changed.

## Root cause

`LowerStaticMemRefViewsForCalyxPass` flattened a static identity-layout ranked
function argument immediately and recorded its original shape/strides in
`argumentViews`. Existing recursive `getStaticView` branches handled
`memref.reinterpret_cast`, `memref.expand_shape`, and
`memref.collapse_shape`, but not `memref.subview`. The pass also did not collect
subviews for dead-view cleanup.

Consequently, a load/store/copy through the subview could not be rewritten to
the flattened base. The subview survived while its source `%source` changed
from `memref<64x64xi64>` to `memref<4096xi64>`. Post-pass verification then
compared its two offsets against a rank-1 source and failed:

```text
error: expected 1 offset values, got 2
note: ... (memref<4096xi64>) -> memref<64x1xi64, strided<[64, 1]>>
```

Leaving an unsupported subview in place was not by itself sufficient: if its
root argument were still flattened, the supposedly explicit unsupported op
would be invalid. The implementation therefore preflights live subview use
chains and protects their root arguments whenever the subview cannot be
resolved and fully eliminated by the existing load/store/copy rewrites.

## Systematic debugging evidence

The authenticated predecessor objects were read before changes:

- exact Task 3 input:
  `reproducers/tinystories-1m-exact-flat-scf-memref/task3-earliest-remaining/input.mlir`;
- exact Task 3 signature:
  `6149b92a9d179ef65caa53ff8dd33259b3d0c05085e5289384627b80c931f693`;
- archived diagnostic: `expected 1 offset values, got 2`;
- exact pipeline:
  `builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`.

The exact 200-byte predecessor reproducer was replayed directly before any
production edit with the authenticated baseline plugin. It exited `1` and
reproduced the exact diagnostic and generic invalid operation with
`memref<4096xi64>` as source.

The single root-cause hypothesis was then tested with behavioral REDs rather
than source-text assertions: if missing recursive subview composition and
premature argument mutation are causal, exact/static cases should fail at the
changed source rank, while the desired pass should emit parsed flattened
accesses and preserve live unsupported inputs without flattening their source.
Every observed RED matched that prediction.

## TDD RED

Before the C++ edit, the required command was run against the authenticated
baseline plugin:

```text
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_memref_subview_extension.py -v
```

Result: six tests ran; five failed for the expected missing behavior and one
inconsistent-layout control failed closed at MLIR input verification as
intended.

The five semantic/safety REDs were:

- the exact Task 3 reproducer: exit `1`, `expected 1 offset values, got 2`;
- live exact mapping `64*i0+i1`: same rank diagnostic;
- live nonzero mapping `64+128*i0+2*i1`: same rank diagnostic;
- live rank-reducing control: same rank diagnostic, proving the baseline
  mutated its source rather than leaving it explicit;
- live dynamic-offset control: same rank diagnostic, proving the same unsafe
  mutation.

A later coverage audit found that the first suite did not exercise the plan's
copy requirement. A real source-subview to target-subview copy regression was
added and explicitly forced against the authenticated baseline plugin before
it was credited. It failed at the same changed argument rank. Against the new
plugin it is lowered to two `scf.for` dimensions with flattened load/store
accesses, and both subviews plus `memref.copy` disappear.

The layout control originally demanded parseable output for a result type that
MLIR itself rejects before the pass. That test was corrected before production
edits to assert the actual fail-closed boundary:
`mismatch of result layout` and no output.

## Narrow implementation

The new `getStaticView(memref::SubViewOp)` branch precedes the generic memref
fallback and accepts only:

- a recursively resolvable source view;
- fully static offsets, sizes, and strides;
- source-view rank equal to result rank, with all metadata vectors at that
  same rank;
- a static result shape exactly equal to `static_sizes`;
- a fully static strided result layout exactly equal to the composed offset and
  strides.

The composition is:

```text
composedOffset = sourceView.offset
               + sum(offset[d] * sourceView.strides[d])
composedStride[d] = sourceView.strides[d] * subviewStride[d]
```

and returns the existing base, static sizes, and composed strides. Dynamic
sentinels, rank reduction, unresolved sources, dynamic/non-strided layouts,
shape mismatch, or layout mismatch return `std::nullopt`.

Before changing argument types, the pass builds prospective views for all
flattenable arguments and checks each live subview plus its transitive
reinterpret/expand/collapse/subview users. A subview root is protected from
flattening unless every live leaf is an existing rewriteable load, store, or
shape-compatible copy. The decision is memoized per view value.

Loads, stores, and copies are then rewritten through the unchanged access
materialization path. All supported view kinds are collected together and
visited in reverse use order; an operation is erased only when `use_empty()`.
A live unsupported subview is never erased, and its protected root argument is
never retagged to rank 1.

## Exact post-pass IR and complete affine proofs

The tests invoke the real plugin, require the output to parse with the pinned
`mlir-opt`, inspect generic post-pass IR, and independently reconstruct the
arithmetic DAG. Multiplication is accepted as affine only when one operand is a
constant. Expected coefficients, offsets, domains, base identities, and roles
are literal hand-derived values; no sample point is used.

### Exact identity/offset case

Input domain:

```text
i0 in [0,64), i1 in [0,1)
```

Exact emitted body:

```mlir
%c64 = arith.constant 64 : index
%0 = arith.muli %arg1, %c64 : index
%1 = arith.addi %0, %arg2 : index
memref.store %arg3, %arg0[%1] : memref<4096xi64>
%2 = memref.load %arg0[%1] : memref<4096xi64>
```

Complete reconstructed formula for both memory operations:

```text
offset = 0
coefficients = [64, 1]
linear index = 64*i0 + i1
base argument = 0
store base role = target
load base role = source
```

### Nonzero offset/stride case

Input domain:

```text
i0 in [0,16), i1 in [0,8)
```

Exact emitted body:

```mlir
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

Complete reconstructed formula for both memory operations:

```text
offset = 64
coefficients = [128, 2]
linear index = 64 + 128*i0 + 2*i1
base argument = 0
store base role = target
load base role = source
```

Both supported outputs parse and contain no `memref.subview`. The exact Task 3
one-operation output is:

```mlir
module {
  func.func @representative(%arg0: memref<4096xi64>) {
    return
  }
}
```

The copy case contains no `memref.subview` or `memref.copy`; generic IR has two
`scf.for` operations and one flattened source load plus one flattened target
store.

## Unsupported and fail-closed behavior

- Rank-reducing control: pass exit `0`, output parses, source stays
  `memref<64x64xi64>`, `memref.subview` and its live load stay explicit, and
  `memref<4096xi64>` is absent.
- Dynamic-offset control: pass exit `0`, output parses, source stays
  `memref<64x64xi64>`, `memref.subview` stays explicit, and
  `memref<4096xi64>` is absent.
- Inconsistent result layout: MLIR input verification exits nonzero with
  `mismatch of result layout`; no output is accepted or claimed legalized.
- Dynamic sizes/strides, dynamic result layouts, unresolved sources, and
  mismatched static shape/layout follow the same `std::nullopt` fail-closed
  branch. They are outside this extension.

The pass does not mutate any subview result type in place. Only arguments whose
live subview chains are fully supported and eliminable are flattened.

## Plugin identities

Authenticated baseline:

- path:
  `/nix/store/p01jw41h2jm2pr8xxww3acrjgx5rl1qn-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`;
- bytes: `21,714,240`;
- SHA-256:
  `6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744`.

Verified rebuilt plugin:

- output:
  `/nix/store/62550m8h4pv2jzmnn46c66rgdvzpjw4g-llm2fpga-mlir-passes-0.1.0`;
- plugin bytes: `21,720,736`;
- SHA-256:
  `d745a77d396639836b6cebfbbeed2fa154f675781cc68c9fef72e316c2362580`.

The digests differ, as required.

The task plan and dispatch named `nix build .#mlir-passes -L`; that command was
run and failed before compilation because this flake exposes no such output.
`nix flake show` and `flake.nix` identify the same single
`nix/mlir-passes.nix` derivation as `packages.x86_64-linux.llm2fpgaMlirPasses`.
Only that derivation was built with:

```text
nix build .#llm2fpgaMlirPasses -L
```

No wider pipeline output was built.

## GREEN verification

Fresh pre-commit gate on the committed implementation tree:

```text
nix build .#llm2fpgaMlirPasses -L
```

PASS; the single plugin derivation is realized.

```text
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_memref_subview_extension.py \
  tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_flat_scf_stage_uses_mlir_flatten_memref_for_expand_shape_reproducer \
  tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_pre_calyx_uses_checked_in_mlir_pass_plugin \
  tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_current_calyx_memref_view_port_blocker_is_minimized \
  -v
```

Result: `Ran 10 tests`, `OK` (all seven new behavioral tests and three relevant
existing integration assertions).

Also PASS:

- `python -m py_compile tests/test_tinystories_1m_exact_memref_subview_extension.py`;
- `git diff --check`;
- the installed repository pre-commit hygiene hook accepted implementation
  commit `e61d08d`.

A broader pre-existing file-assertion suite ran 36 tests and exposed two
unrelated failures:

- `test_calyx_sv_script_does_not_use_handshake` conflicts with checked-in
  handshake repair names already present in
  `scripts/pipeline/calyx_to_sv_no_handshake.sh`;
- `test_current_calyx_math_rsqrt_blocker_is_minimized` expects two phrases
  absent from the checked-in `reproducers/calyx-math-rsqrt/README.md`.

Those test, script, and README paths have no diff from assigned base `edd4acb`.
They were not changed or hidden by Task 2. The three static-memref/pass cases in
that same suite pass and are included in the fresh gate above.

## Files

Implementation commit `e61d08d` contains exactly:

- `tools/mlir-passes/FoldConstantTruncFOps.cpp`;
- `tests/test_tinystories_1m_exact_memref_subview_extension.py`;
- `reproducers/tinystories-1m-exact-static-subview-extension/identity-offset.mlir`;
- `reproducers/tinystories-1m-exact-static-subview-extension/nonzero-offset-stride.mlir`;
- `reproducers/tinystories-1m-exact-static-subview-extension/unsupported-rank-reducing.mlir`;
- `docs/results/2026-09-01-tinystories-1m-static-subview-extension.md`.

This implementer report is the only report-only follow-up file.

## Residual risks and explicit non-claims

- The complete 18,933,168-byte retained c22 flat-SCF artifact was not run;
  authenticated full replay and its next frontier are Task 3 scope.
- No valid normalized full artifact, zero-blocker census, Nix stage
  registration, or Calyx eligibility is claimed.
- Integer overflow for theoretical extreme static offsets/strides is not newly
  diagnosed. The exact tested shapes are small and the result layout must
  exactly match MLIR's verified static layout.
- View kinds outside reinterpret/expand/collapse/subview remain unsupported.
- The argument-protection root tracer follows the existing recursive view
  model. Unsupported view flow through unrelated region-carried block
  arguments is not generalized in this task.
- The two unrelated legacy file-assertion failures above remain present at the
  assigned base and are outside Task 2.
