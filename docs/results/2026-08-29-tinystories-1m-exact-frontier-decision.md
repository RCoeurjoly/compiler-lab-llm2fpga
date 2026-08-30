# Exact TinyStories-1M frontier decision

## Decision

Select exactly one response class: **`compiler_pass`**.

The accepted Task 5 evidence commit is
`3418f989fec7996561f4e59ba6a6d902c1fb02a5`. Its deterministic frontier receipt
is the on-disk file
`artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json`
with SHA-256
`b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55`
and receipt self-hash
`af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b`.
It identifies `torch_mlir_frontier`: export succeeds, while the registered
`...-torch` stage fails before Linalg with an illegal `torch.operator`.

The minimal, exact-interestingness-verified reproducer is the 334-byte
`reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir`
(SHA-256 `285a40e0ba9dd999fb4155c465889e1b3fa2dc0768716328bc7e4c8898bc4b37`).
It contains exactly the original operation and types:

```mlir
torch.operator "torch.aten.bitwise_right_shift.Tensor_Scalar"
  (%arg0, %int1) : (!torch.vtensor<[4,1],si64>, !torch.int)
  -> !torch.vtensor<[4,1],si64>
```

The pinned `torch-mlir-opt` reproduces the diagnostic. The pinned generated
Torch operation definitions contain tensor/tensor right shift but no
`bitwise_right_shift.Tensor_Scalar` spelling. Crucially, the failure is inside
`torchdynamo-export-to-torch-backend-pipeline`, called by Python
`export_and_import`; it happens before any project-side downstream MLIR pass
could run. Thus the next follow-up must add a narrow Torch-MLIR
frontend/legalization pass or pinned-source patch at that point.

## Required semantics and scope

The follow-up accepts only `Tensor_Scalar` with a signed `si64` tensor and a
scalar shift in `[0, 62]`. It must broadcast the scalar shift and lower to a
sign-preserving arithmetic right shift (such as elementwise `arith.shrsi`),
without narrowing either operand. Negative values therefore retain arithmetic
shift behavior: `-5 >> 1 == -3`; `-1 >> 1 == -1`.

This is not a rounding operation. The adapter separately expresses its
ties-away-from-zero fixed-point rounding in `round_shift_signed` with
quotient/remainder logic. The pass must not replace the bitwise shift with
truncating division, nearest rounding, a logical shift, or that separate
rounding helper. It must reject out-of-contract shift counts rather than
silently redefining them.

No model, adapter, package, contract, fixture, backend, scheduling, runtime,
or RTL modification is authorized by this decision. The expected improvement
is only that the reduced operation legalizes and the registered pipeline moves
beyond the existing Torch-MLIR frontier; any later frontier is new evidence,
not a success claim for later stages.

## Causal rejection of the other classes

`bit_accurate_primitive` is rejected: signed integer arithmetic shift is a
standard compiler operation, and no valid compiler artifact exists from which
to justify a new model-specific hardware primitive. Adding RTL now would
bypass the frontend failure.

`scheduling_or_memory_architecture` is rejected: there is no valid Linalg,
SCF, Calyx, RTL, resource, or timing result. Buffering, reuse, streaming, and
scheduling occur after the causal boundary and cannot legalize an illegal
Torch-MLIR operation.

`autoregressive_runtime_boundary` is rejected: the import fails for one
exported tensor program before a generated token lifecycle or runtime
composition exists. A runtime boundary cannot repair this operator and would
expand scope prematurely.

## Red/green regressions for the follow-up

Red, pinned reproducer (observed now; exit 1):

```text
nix develop -c torch-mlir-opt -pass-pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=})' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir -o /dev/null
```

It must report `failed to legalize operation 'torch.operator' that was
explicitly marked illegal` before the compiler change. After the pass/source
patch, run the same command; it must exit 0, contain no generic
`torch.operator` for this operation, and preserve the signed-si64
arithmetic-shift cases above.

Red, registered stage (observed now; exit 1 with the same diagnostic):

```text
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
```

Green uses the same registered command after the compiler change. It must exit
0 with a nonempty Torch-MLIR artifact, no matching legalization diagnostic,
and unchanged Task 1--3 identity hashes. The later Linalg/SCF/Calyx stages are
intentionally not green criteria for this task.

The retained identities are the Task 1 audit file/payload
`3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd` /
`7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766`;
Task 2 artifact file/payload/model receipt
`173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a` /
`af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838` /
`5e56907e60c83c5d98b3c3fe88772b7dfba71e53a9435de548a9d54ea7497834`;
and Task 3 generation file/artifact/result
`e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3` /
`9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3` /
`c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644`.

## Binding checks

```text
nix develop -c python -m json.tool artifacts/comparison/tinystories-1m-exact-frontier-decision.json
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
```

The first command checks JSON syntax; the second independently verifies the
Task 5 bundles from which `frontier_hash` was taken. The decision JSON has a
canonical self-hash over all fields except `sha256`; its one-item `selection`
array and `selected_response_class_count: 1` make the one-class decision
machine-checkable without introducing a new implementation artifact.
