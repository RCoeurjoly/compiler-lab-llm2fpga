# Calyx Arith Truncf Constant Reproducer

This is the minimized reproducer for the current direct-Linalg no-handshake
`calyx` blocker.

The failing command is:

```sh
circt-opt input.mlir --lower-scf-to-calyx='top-level-function=main'
```

The blocker is a live constant truncation:

```mlir
%value = arith.truncf %cst64 : f64 to f32
```

CIRCT Calyx lowering marks `arith.truncf` illegal. The companion
`f32-constant.mlir` shows that the equivalent live `f32` constant lowers to
Calyx, so the next acceptable fix is either:

- avoid producing these `f64` constants before Calyx through an allowed dialect
  path, or
- add a real MLIR pass that folds constant `arith.truncf` operations to `f32`
  constants before `--lower-scf-to-calyx`.

Do not fix this with textual MLIR rewriting.
