# Task 5 report: exact current-pipeline frontier

## Status

Implemented and evidenced against accepted Task 4 commit
`7eed3592a661c0cb3c417dc59b29839266446b2d`.

The earliest causal invalid stage is `torch-mlir`, classified as
`torch_mlir_frontier`. Its exact terminal diagnostic is:

```text
failed to legalize operation 'torch.operator' that was explicitly marked illegal
```

The minimal reproducer identifies
`torch.aten.bitwise_right_shift.Tensor_Scalar` as one exact operation retaining
that diagnostic. Linalg and every later stage were not run.

## Delivered evidence

- strict earliest-frontier classifier and CLI receipt generator;
- classifier RED/GREEN tests plus static receipt/hash tests;
- live-Nix-bound machine receipt;
- terminal-content-preserving Nix failure log;
- full failing IR archive with compressed and content hashes;
- 334-byte one-operation reproducer and exact interestingness test;
- human-readable result report.

Every stage record binds a nonempty artifact, exact command, tool and
derivation revisions, named log plus log hash, parsed terminal diagnostics,
exit code, and upstream identity. The Torch-MLIR artifact is explicitly
rejected; no partial output is promoted.

## Commands and observations

The brief's `...-torch-mlir` attribute is absent. The receipt preserves that
flake-resolution diagnostic and records resolution to the registry's actual
logical Torch-MLIR suffix, `...-torch`.

`nix build .#tiny-stories-1m-kev-gpt-exact-torch -L` entered Torch-MLIR and
failed deterministically at `model_adapter_exact_package.py:879:0`. The
derivation log and a Nix-contained reproduction both reported the same illegal
`torch.operator` diagnostic.

The available `mlir-reduce` cannot parse this newer registered Torch dialect
(MLIR 21 reducer versus LLVM 23 Torch-MLIR). A manual delta reduction retained
one original operation, name, types, and pass pipeline and reproduced the same
error.

## Scope and concerns

No backend, model, quantization, DDR, PCIe, compiler lowering, or RTL change
was made. The missing brief alias should be corrected in a later planning or
registration task, but it did not replace or mask the factual compiler
frontier because the actual registered stage was run. A future compiler task
should address integer tensor shift legalization at the Torch-MLIR boundary
and prove the full model advances before invoking Linalg.
