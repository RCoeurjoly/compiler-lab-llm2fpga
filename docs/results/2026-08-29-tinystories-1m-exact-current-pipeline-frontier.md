# Exact TinyStories-1M current-pipeline frontier

## Result

The unchanged registered pipeline reaches its first causal invalid stage at
`torch-mlir`. The classification is `torch_mlir_frontier`:

```text
failed to legalize operation 'torch.operator' that was explicitly marked illegal
```

The preserved TorchFX-to-Torch-MLIR input contains illegal generic
`torch.operator` nodes for integer tensor shifts. A one-operation reduction
retains the diagnostic with
`torch.aten.bitwise_right_shift.Tensor_Scalar`. The current Torch-MLIR pass
pipeline therefore cannot legalize an operation required by the authenticated
exact integer/fixed-point program.

No Linalg, SCF, flat-SCF, Calyx, or SystemVerilog command was run after this
failure. This report makes no claim about those later stages.

## Stage evidence

| Stage | Status | Bound artifact | SHA-256 | Terminal result |
| --- | --- | --- | --- | --- |
| `pytorch-exported` | succeeded | `exported.pt2`, 69,510,766 bytes | `6c9d2931a18811560f6565e9d313390fb5e0b7b167af39ddc094e19b949ce085` | exit 0; zero error diagnostics |
| `torch-mlir` | compiler failure | rejected full failing IR capture, 12,121,418 bytes uncompressed | `a9a663989a35f3d9e2984486db81a82c2aa7bfff421ec56a8558f99a22f52eb0` | exit 1; illegal `torch.operator` |

Each receipt record also binds its exact Nix builder command, derivation and
input derivations, source/tool revisions, log identity, exit code, parsed
terminal diagnostics, and upstream identity. The full receipt is
[`tinystories-1m-exact-current-pipeline-frontier.json`](../../artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json).

The failed stage did not produce an accepted Torch-MLIR output. The full
failure input is retained only as a rejected diagnostic artifact; it is not a
successful stage output and cannot be used to justify a downstream build.

## Minimal reproducer

The full emitted input was 12,121,418 bytes and contained 1,755 generic
`torch.operator` nodes. The accepted reduction is 334 bytes:

- full input content SHA-256:
  `a9a663989a35f3d9e2984486db81a82c2aa7bfff421ec56a8558f99a22f52eb0`;
- deterministic gzip archive SHA-256:
  `4f378cf9d66c46396ee7744c4c360d5bb29bf06a8ac3cdf6527b249aef41ee67`;
- reduced IR SHA-256:
  `285a40e0ba9dd999fb4155c465889e1b3fa2dc0768716328bc7e4c8898bc4b37`.

Run the exact interestingness check with:

```bash
nix develop -c reproducers/tinystories-1m-exact-torch-mlir/interesting.sh \
  reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir
```

The packaged `mlir-reduce` is LLVM/MLIR 21 while Torch-MLIR is built against
LLVM 23. `mlir-reduce` could not register or permit the Torch dialect, so an
automated reduction was unsupported. The manual delta reduction copied one
original failing operation with its original name and types, removed unrelated
operations, and was accepted only after the exact pass pipeline reproduced the
same terminal diagnostic.

## Command resolution and failure classification

The task brief names the first target
`tiny-stories-1m-kev-gpt-exact-torch-mlir`, but the model registry exports the
logical Torch-MLIR artifact as `tiny-stories-1m-kev-gpt-exact-torch`. The first
spelling fails at flake attribute resolution. That diagnostic is preserved in
the receipt, then the actual registered `-torch` stage was executed. Because
that registered derivation entered Torch-MLIR and produced a deterministic
compiler legalization error, the final result is a compiler frontier, not a
Nix/environment failure.

## Scope

The run consumed accepted exact-export commit
`7eed3592a661c0cb3c417dc59b29839266446b2d`. It made no backend, model,
quantization, DDR, PCIe, lowering, scheduling, or RTL change. Partial output is
not accepted. Downstream functional, resource, timing, and board claims remain
false.
