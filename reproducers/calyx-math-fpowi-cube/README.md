# Calyx `math.fpowi` Cube Reproducer

This MRC preserves the scalar f32 `math.fpowi` signature observed in the frozen
W8A8 RC, including its constant exponent `3 : i64`.

```sh
circt-opt reproducer/calyx-math-fpowi-cube/input.mlir \
  --lower-scf-to-calyx='top-level-function=main'
```

It is a compiler-capability probe, not numerical-equivalence evidence.
Algebraic strength reduction is not asserted exact, and textual MLIR
substitution and the resource-scout nonlinear pass are not acceptable fixes.
