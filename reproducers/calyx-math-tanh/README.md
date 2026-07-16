# Calyx `math.tanh` Reproducer

This MRC preserves the scalar f32 `math.tanh` signature observed in the frozen
W8A8 RC.

```sh
circt-opt reproducer/calyx-math-tanh/input.mlir \
  --lower-scf-to-calyx='top-level-function=main'
```

It is a compiler-capability probe, not numerical-equivalence evidence. Textual
MLIR substitution and the resource-scout nonlinear pass are not acceptable
fixes.
