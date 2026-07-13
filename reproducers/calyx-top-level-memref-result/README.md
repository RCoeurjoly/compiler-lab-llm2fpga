# Calyx Top-Level Memref Result Wrapper Reproducer

This reproducer checks the interface emitted by the repository-packaged
SCF-to-Calyx lowering for a function with a top-level `memref` argument and an
`i32` result.

## Upstream command

`flake.lock` pins the CIRCT source used by the root `circt-nix` package to
[`llvm/circt` revision `5dc62fe46c9dbf8936f4f706083301e7503715eb`](../../flake.lock).
The package resolved by the command below is
`circt-1.144.0g20260331_5dc62fe`.

```bash
CIRCT=$(nix build .#circt --no-link --print-out-paths)
"$CIRCT/bin/circt-opt" \
  reproducers/calyx-top-level-memref-result/input.mlir \
  --lower-scf-to-calyx='top-level-function=kernel' \
  -o reproducers/calyx-top-level-memref-result/output.calyx.mlir
```

`output.calyx.mlir` is unedited tool output from this command.

## Observed interfaces

The inner component retains the scalar result:

```mlir
calyx.component @kernel(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go})
    -> (%out0: i32, %done: i1 {done})
```

The generated top-level wrapper exposes only its control interface:

```mlir
calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go})
    -> (%done: i1 {done})
```

The checked-in output demonstrates that this lowering retains `out0: i32` on
the inner `kernel` component but does not expose an `out0` port on the generated
`main` wrapper.
