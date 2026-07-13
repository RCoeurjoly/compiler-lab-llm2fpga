# Calyx Memref-Result Wrapper Reproducer Design

## Objective

Determine whether upstream CIRCT `--lower-scf-to-calyx` discards scalar
results when it creates a top-level wrapper for a function with a `memref`
argument.

## Input

Add a minimal function named `kernel`:

```mlir
func.func @kernel(%memory: memref<4xi32>) -> i32 {
  %c0 = arith.constant 0 : index
  %value = memref.load %memory[%c0] : memref<4xi32>
  return %value : i32
}
```

The input has exactly the two properties under investigation: an external
memory argument and an observable scalar result.

## Experiment

Run the repository's packaged CIRCT tool with:

```sh
circt-opt input.mlir \
  --lower-scf-to-calyx='top-level-function=kernel'
```

Preserve the generated Calyx MLIR as observed evidence. Do not edit the output
or add a workaround in this experiment.

## Assertions

Inspect and test whether:

1. The lowered inner `kernel` component retains an `i32` output port.
2. A new top-level `main` component is generated because `kernel` accepts a
   `memref` argument.
3. The generated `main` component has control ports but no functional result
   port.
4. `main` instantiates or invokes `kernel` without forwarding its scalar
   result to a top-level output.

The regression records the observed upstream behavior. It does not encode the
behavior as desirable and does not implement a fix.

## Deliverables

- `reproducers/calyx-top-level-memref-result/input.mlir`
- `reproducers/calyx-top-level-memref-result/output.calyx.mlir`
- `reproducers/calyx-top-level-memref-result/README.md`
- A repository test that checks the input, command, and observed output shape.

## Success Criteria

The reproducer is complete when the packaged upstream pass runs successfully
and the checked-in evidence unambiguously confirms or refutes result loss at
the generated top-level `main` boundary.
