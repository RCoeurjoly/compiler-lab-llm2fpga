# Full W8A8 Calyx Frontier Design

## Objective

Advance the existing full `tinystories-w8a8` PT2E W8A8,
Direct-Linalg, no-handshake route through its next factual compiler frontier
without adding TOSA, changing the PyTorch model or calibration, or changing
the provisional math-scout policy.

The immediate target is a valid Calyx MLIR artifact. Native SystemVerilog,
RTLIL, FPGA mapping, and place-and-route remain strictly downstream of that
artifact.

## Evidence and diagnosis

`flat-scf` did not fail to execute: `mlir-opt --flatten-memref` produced its
artifact. Its diagnostic script labels the artifact `blocked` whenever it
finds residual `memref.reinterpret_cast`, `memref.expand_shape`,
`memref.collapse_shape`, or `memref.copy` operations.

For this full model, the raw flat-SCF output contains 339 reinterpret casts,
43 expands, 13 collapses, and 115 copies. The existing pre-Calyx
`llm2fpga-lower-static-memref-views-for-calyx` pass removes all of those from
the actual input handed to CIRCT. The flat-SCF diagnostic is therefore a
non-terminal normalization warning for this route, not the current compiler
frontier.

The normalized input contains exactly one remaining operation that CIRCT
rejects:

```mlir
%float = arith.uitofp %predicate : i1 to f32
```

It implements the boolean causal-mask multiplier. The pinned SCF-to-Calyx
conversion supports `arith.extui`, `arith.sitofp`, `arith.select`, and f32
arithmetic, but does not list `arith.uitofp` as a supported operation.

## Chosen design

Add a narrow, exact pre-Calyx MLIR legalization pass named
`llm2fpga-lower-i1-uitofp-for-calyx`.

It rewrites only `arith.uitofp` with source type `i1` and result type `f32`:

```mlir
%integer = arith.extui %predicate : i1 to i32
%float = arith.sitofp %integer : i32 to f32
```

This is semantically exact because the domain of `i1` is only `{0, 1}`. The
intermediate signed i32 representation therefore preserves the source value,
and its conversion to f32 produces exactly `0.0` or `1.0`.

The pass must not rewrite arbitrary wider `arith.uitofp` operations: replacing
an unsigned wider value with a signed conversion can change values whose high
bit is set. It must also leave non-f32 result types unchanged.

Place the pass after all existing pre-Calyx normalizations and before the final
`canonicalize,cse`, so the boundary handed to CIRCT has no remaining
`arith.uitofp i1 -> f32` operation.

## Flat-SCF reporting correction

Keep the residual report, but change its manifest status from `blocked` to
`completed-with-residuals`. The report remains an input-quality signal and
lists the operations requiring the pre-Calyx normalizer; it no longer implies
that the route stopped at flat-SCF.

Add an explicit pre-Calyx legality census to the Calyx-stage evidence. It must
report the residual view/copy operations and `arith.uitofp` separately from
the generic floating-point count. The full-model Calyx handoff must assert
that the four view/copy forms and `arith.uitofp` are absent after the
normalizer and new legalization pass.

## Verification

1. Add an in-tree minimal reproducer showing that the pinned CIRCT
   `--lower-scf-to-calyx` rejects `arith.uitofp i1 -> f32`.
2. Add a lowered counterpart using `arith.extui` followed by `arith.sitofp`;
   the same CIRCT lowering must accept it.
3. Add a plugin-level test that verifies the pass is registered, matches only
   the `i1`-to-`f32` form, and materializes the two exact replacement ops.
4. Update the flat-SCF diagnostic tests for `completed-with-residuals` and
   retain the residual counts.
5. Build the full frozen model through `...-calyx` without a short cutoff.
   Record the next factual frontier or generated Calyx artifact.
6. Only if Calyx succeeds, continue in order through native SV, the existing
   staged XC7K480T mapper, and nextpnr-xilinx. Do not substitute TOSA or a
   smaller model.

## Alternatives rejected for this iteration

- **Patch CIRCT for arbitrary `arith.uitofp`:** technically valuable as a
  future upstream contribution, but it expands the current change into a
  maintained toolchain fork and is unnecessary for this exact boolean case.
- **Rewrite the model or PyTorch graph:** would hide a compiler-interface gap,
  alter the reference path, and confound the full-model experiment.
- **Proceed to SV using a placeholder:** would create invalid resource
  evidence; downstream stages must remain gated on a real Calyx artifact.

## Non-goals

- No functional-equivalence, board, SmoothQuant, TOSA, model, calibration, or
  math-scout-policy change.
- No general unsigned-integer-to-float legalization.
- No arbitrary timeout, garbage collection, or transient `/tmp` evidence.
