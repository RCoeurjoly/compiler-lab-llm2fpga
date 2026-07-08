# Flat SCF Expand Shape Materialization Reproducer

This is the minimized reproducer for the old direct-Linalg no-handshake
`flat-scf` blocker.

The failing CIRCT command was:

```sh
circt-opt input.mlir --flatten-memref --canonicalize --cse
```

It failed because CIRCT `--flatten-memref` left a live materialization from
`memref<2xf32>` back to `memref<1x1x2xf32>` when the original allocation still
had a `memref.expand_shape` user.

The current pipeline uses upstream MLIR `mlir-opt --flatten-memref` for this
stage. That pass handles this reproducer and lets the representative-core
pipeline advance to the Calyx lowering stage.
