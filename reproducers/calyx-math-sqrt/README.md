# Calyx `math.sqrt` Supported-Control Reproducer

This MRC preserves the scalar f32 `math.sqrt` signature used as the
supported-control operation for the frozen W8A8 RC.

```sh
circt-opt reproducer/calyx-math-sqrt/input.mlir \
  --lower-scf-to-calyx='top-level-function=main'
```

It is a compiler-capability probe, not numerical-equivalence evidence. It does
not prove that the local `math.rsqrt -> 1 / math.sqrt` bridge preserves PT2E
results. Textual MLIR substitution and the resource-scout nonlinear pass are
not acceptable fixes.
