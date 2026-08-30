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
and unchanged Task 1--3 identity hashes. It is not sufficient to inspect the
MLIR or assert that a generic operator disappeared: the green gate must also
evaluate the lowered shift implementation and compare its exact results to the
semantic fixture below. The later Linalg/SCF/Calyx stages are intentionally not
green criteria for this task.

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

## Executable signed-shift semantic contract

[`tinystories-1m-exact-shift-semantics.json`](../../artifacts/comparison/tinystories-1m-exact-shift-semantics.json)
is a deterministic fixture with file SHA-256
`2aadecfedbbf93a617890d21586d17456f945028d866c368c15af754471f3064`
and canonical self-hash
`4490ddcf0e6f59eed32ecfe31482dc142c9907f4e74efe32154a99d5651ef17f`.
Its independent Python interpreter is the semantic oracle; it deliberately
does not accept mere lowering success as proof of arithmetic behavior.

The required valid tensor/scalar broadcast cases are all one-dimensional
signed `si64` tensors with exact output dtype and shape preserved:

| Case | Input | Scalar shift | Expected output | Expected output SHA-256 |
| --- | --- | ---: | --- | --- |
| `shift_one` | `[-5, -1, 0, 1, 5]` | 1 | `[-3, -1, 0, 0, 2]` | `f949ee74a7ad05711fbb6565bf80cebe207070bc9dc95c87dedfaac63c5988eb` |
| `shift_zero` | `[-5, -1, 0, 1, 5]` | 0 | identical input | `b197b99b9f460091bbe36cd35870dfdb83e53fdd3cc547ac25e43e34c7f72fce` |
| `shift_sixty_two` | `[-4611686018427387904, -1, 0, 4611686018427387904]` | 62 | `[-1, -1, 0, 1]` | `5e7024c18da1979c0b25c41fd058d533df916005f9ffa6e3d31a449d1c89d605` |

The scalar shift is broadcast to every element. `negative_shift` (`-1`) must
produce exactly status `rejected_negative_shift` and diagnostic
`shift_contract:negative_shift`; `shift_greater_than_sixty_two` (`63`) must
produce exactly status `rejected_shift_greater_than_sixty_two` and diagnostic
`shift_contract:greater_than_sixty_two`. Neither invalid case may compile,
produce output, or mask its count.

The compiler follow-up must emit
`artifacts/comparison/tinystories-1m-exact-shift-lowered-results.json` using
schema `tinystories-1m-exact-shift-lowered-results-v1`, with one record per
fixture case. Valid records have `status: "ok"` and exact `dtype`, `shape`, and
`values`; invalid records have the exact status/diagnostic above and no output.
Its mechanical full-stage green gate is:

```text
stage="$(nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch)" && nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py --lowered-result artifacts/comparison/tinystories-1m-exact-shift-lowered-results.json --stage-artifact "$stage"
```

The verifier checks the successful nonempty registered artifact and reloads the
current Task 1 audit, Task 2 model artifact, and Task 3 generation receipt. It
compares their file and embedded payload/result hashes mechanically against the
decision receipt before accepting evaluated lowering results.

## Binding checks

```text
nix develop -c python -m json.tool artifacts/comparison/tinystories-1m-exact-frontier-decision.json
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier_semantics.py -v
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py
```

The first command checks JSON syntax; the second independently verifies the
Task 5 bundles from which `frontier_hash` was taken. The decision JSON has a
canonical self-hash over all fields except `sha256`; its one-item `selection`
array and `selected_response_class_count: 1` make the one-class decision
machine-checkable. The semantic fixture and its exact expected output hashes
are also bound into that decision self-hash without introducing a compiler
implementation artifact.
