# Calyx `arith.uitofp i1 -> f32` frontier

This is the minimal in-tree reproducer for the pinned CIRCT SCF-to-Calyx
conversion rejecting `arith.uitofp` from `i1` to `f32`.

Run it with the pinned toolchain:

```sh
circt-opt input.mlir --lower-scf-to-calyx='top-level-function=main'
```

The conversion rejects the input because its operation groups do not legalize
`arith.uitofp`. This is distinct from a generic unsigned-to-float lowering:
an `i1` value is exactly either 0 or 1, so the compiler-local, exact form is
`arith.extui i1 -> i32` followed by `arith.sitofp i32 -> f32`.

Textual MLIR substitution is not an acceptable fix. The production route must
apply the checked-in MLIR pass that recognizes only this exact source and
result type pair. Wider unsigned inputs must remain unchanged because a signed
intermediate would not preserve their high-bit values.
