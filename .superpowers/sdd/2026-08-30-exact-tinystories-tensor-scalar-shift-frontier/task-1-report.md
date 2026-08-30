# Task 1 report: Torch-MLIR Tensor-Scalar right-shift legalization

## Status

**DONE_WITH_CONCERNS**

The exact signed-si64 `torch.aten.bitwise_right_shift.Tensor_Scalar` frontier is
legalized without changing the model adapter or its semantics. The reduced
reproducer lowers through the pinned Torch-MLIR backend to `arith.shrsi`; the
full authenticated import contains no generic right-shift operation immediately
before `torch-reduce-op-variants`. The full registered stage now stops at the
distinct next frontier, `torch.aten.bitwise_left_shift.Tensor_Scalar`.

The controller ruled that the accepted decision's earliest-frontier rule
overrides Task 1 brief Step 4's predicted full-stage exit 0. Task 1 must not be
broadened to left shift. This result is therefore complete with the concern
that a new bounded compiler-frontier follow-up is required before semantic Task
2 can run.

## Exact commits

- `7769eec3924fe4b900b5ba5a323104b03419e7c8`
  (`feat: legalize exact signed tensor scalar shifts`) — verified
  implementation, pinned-source wiring, and focused tests.
- The report itself is committed separately; its exact containing commit is
  recorded in the task handoff because a file cannot contain its own commit ID.

## Files changed

- `patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch`
- `torch-mlir.nix`
- `tests/test_tinystories_1m_exact_shift_legalization.py`
- `.superpowers/sdd/2026-08-30-exact-tinystories-tensor-scalar-shift-frontier/task-1-report.md`

No model, adapter, package, contract, reference fixture, project pipeline,
backend, runtime, RTL, `flake.nix`, or `nix/pipeline.nix` file changed.

## Red evidence

The repository pre-check ran before editing:

```text
scripts/agent/pre_final_check.sh
```

Outcome: exit 0 on the clean task worktree.

The new structural suite was run before implementation:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_shift_legalization.py -v
```

Outcome: exit 1; the adapter identity guard passed and six implementation
requirements failed because neither a plugin nor a pinned-source patch existed.

The exact accepted reproducer was run before implementation:

```text
nix develop -c torch-mlir-opt -pass-pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=})' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir -o /dev/null
```

Outcome: exit 1 with `failed to legalize operation 'torch.operator' that was
explicitly marked illegal`.

## Implementation route and plugin/source-patch evidence

The pinned tool advertises generic plugin flags:

```text
/nix/store/80aad3hp8r9wn2k18drwg66j4cykvnck-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt --help-hidden | rg -- '--load-(pass|dialect)-plugin'
```

Outcome: both `--load-pass-plugin` and `--load-dialect-plugin` are present.
The required interface nevertheless is not usable for this pass:

1. An exploratory plugin compiled against the installed pinned headers and
   `libTorchMLIRAggregateCAPI.so`.
2. Loading that plugin did not register its pass in the host
   (`does not refer to a registered pass`). `ldd` showed that the plugin had
   loaded a separate shared `libMLIR.so`, while `torch-mlir-opt` contains its
   MLIR registry statically.
3. Removing the aggregate CAPI linkage allowed the shared object itself to
   link, but `torch-mlir-opt` reported `Failed to load passes ... Request
   ignored.` `ldd -r` showed unresolved MLIR/Torch C++ symbols.
4. The host confirms the missing ABI surface:

```text
ldd /nix/store/80aad3hp8r9wn2k18drwg66j4cykvnck-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt | rg 'MLIR|Torch'
nm -D /nix/store/80aad3hp8r9wn2k18drwg66j4cykvnck-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt | wc -l
nm -D /nix/store/80aad3hp8r9wn2k18drwg66j4cykvnck-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt | rg 'registerPass|OperatorOp7getName|RewriterBase'
```

Outcome: no MLIR/Torch shared dependency, 675 dynamic-symbol table entries,
and zero required registration/operator/rewriter symbols.

Per the controller ruling, the selected route is therefore the smallest
pinned-source patch. It modifies only pinned revision
`59c249e5cc2025acca81bdcf1596b8dd36a5c0f9` and inserts an internal function
pass immediately after `createInlinerPass()` and before
`createReduceOpVariantsPass()` in
`createTorchDynamoExportToTorchBackendPipeline`.

The pass matches only
`torch.aten.bitwise_right_shift.Tensor_Scalar`, requires identical signed-si64
value-tensor input/result types and a direct constant scalar count in `[0, 62]`,
materializes a rank-zero scalar tensor, broadcasts it to the input size, and
replaces the generic operator with the registered tensor/tensor operation. It
fails closed for unsupported signature/dtype, dynamic count, negative count,
or count greater than 62. It does not implement left shift or division.

The first source build exposed one missing explicit `TorchDialect.h` include;
the corrected derivation then built and linked successfully. LLVM (4,127 build
actions) and MLIR (2,714 build actions) prerequisites also completed and were
reused by the final Torch-MLIR build. There was no runtime or ABI failure on
the selected source-patch route.

## Exact build and test commands with outcomes

Patch applicability and package build:

```text
patch -p1 --dry-run -d /nix/store/6ahfs3ba2jhilx68qwx25bh0yvkdw6k3-source < patches/torch-mlir/legalize-bitwise-right-shift-tensor-scalar.patch
nix build --no-link --print-out-paths .#torchMlir
```

Outcomes: dry-run exit 0; build exit 0; output
`/nix/store/80aad3hp8r9wn2k18drwg66j4cykvnck-torch-mlir-0-unstable-2026-02-12`.

Required reduced backend command, using that packaged binary:

```text
/nix/store/80aad3hp8r9wn2k18drwg66j4cykvnck-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt -pass-pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=})' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir -o /tmp/exact-shift-torch-backend.mlir
```

Outcome: exit 0; output is nonempty; no generic right-shift operator remains;
the result is the registered `torch.aten.bitwise_right_shift.Tensor` with a
same-shape signed-si64 shift tensor.

Arithmetic lowering proof:

```text
/nix/store/80aad3hp8r9wn2k18drwg66j4cykvnck-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt -pass-pipeline='builtin.module(func.func(torch-match-quantized-custom-ops), torchdynamo-export-to-torch-backend-pipeline{ extra-library=}, torch-backend-to-linalg-on-tensors-backend-pipeline)' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir -o /tmp/exact-shift-linalg.mlir
rg -n 'arith.shrsi' /tmp/exact-shift-linalg.mlir
```

Outcome: both exit 0; `arith.shrsi %in, %in_0 : i64` occurs in the generated
`linalg.generic`.

Invalid-count and type probes were generated mechanically from the checked-in
reproducer and sent to the same packaged tool/pipeline:

```text
sed 's/torch.constant.int 1/torch.constant.int -1/' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir | <packaged-tool> -pass-pipeline='<accepted-pipeline>' -o /dev/null
sed 's/torch.constant.int 1/torch.constant.int 63/' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir | <packaged-tool> -pass-pipeline='<accepted-pipeline>' -o /dev/null
sed -e 's/(%arg0: !torch.vtensor<\[4,1\],si64>)/(%arg0: !torch.vtensor<[4,1],si64>, %arg1: !torch.int)/' -e '/torch.constant.int 1/d' -e 's/%int1)/%arg1)/' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir | <packaged-tool> -pass-pipeline='<accepted-pipeline>' -o /dev/null
sed 's/si64/si32/g' reproducers/tinystories-1m-exact-torch-mlir/bitwise-right-shift-tensor-scalar.mlir | <packaged-tool> -pass-pipeline='<accepted-pipeline>' -o /dev/null
```

Outcomes: each compiler invocation exits nonzero, respectively reporting
`shift_contract:negative_shift`,
`shift_contract:greater_than_sixty_two`,
`shift_contract:dynamic_shift`, and
`shift_contract:unsupported_dtype`; none produces output.

Final unit suites:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_shift_legalization.py tests/test_tinystories_1m_exact_pipeline_registration.py tests/test_tinystories_1m_exact_frontier_semantics.py -v
```

Outcome: exit 0, 16/16 tests passed.

Full authenticated registered stage:

```text
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
```

Outcome: exit 1 at the newly exposed distinct frontier. A raw import and an IR
dump immediately before `torch-reduce-op-variants` proved that the patched
full model contains zero generic
`torch.aten.bitwise_right_shift.Tensor_Scalar` operations. The exact next
diagnostic is:

```text
/tmp/tinystories-exact-raw.mlir:670:12: error: failed to legalize operation 'torch.operator' that was explicitly marked illegal
note: see current operation: ... name = "torch.aten.bitwise_left_shift.Tensor_Scalar" ... : (!torch.vtensor<[4,64],si64>, !torch.int) -> !torch.vtensor<[4,64],si64>
```

The raw authenticated import had 1,633 generic right shifts and 122 generic
left shifts before the patched backend pipeline. The pre-Reduce IR dump had
zero generic right shifts. This satisfies the controller's earliest-frontier
ruling while explicitly avoiding an unauthorized left-shift implementation.

## Identity-preservation evidence

The following command was run on the final implementation:

```text
sha256sum TinyStories/model_adapter_exact_package.py artifacts/reference/tinystories-1m-exact-input-audit.json artifacts/reference/tinystories-1m-exact-package-model.json artifacts/reference/tinystories-1m-exact-generation.json
git diff --exit-code HEAD -- TinyStories/model_adapter_exact_package.py artifacts/reference/tinystories-1m-exact-input-audit.json artifacts/reference/tinystories-1m-exact-package-model.json artifacts/reference/tinystories-1m-exact-generation.json
```

Outcome: `git diff` exit 0 and the exact accepted file hashes:

- adapter: `d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e`
- Task 1 audit: `3cf8a5b9db8acf0ca04e92277c0f9f07c81900a4c754626183bd1d22063616bd`
- Task 2 model artifact: `173f54586fd37f06e03e9b754568df729591d2cacc5b4a238407ea553d3d529a`
- Task 3 generation receipt: `e611002b083c8ecde9dc7d2bd89a6b41bf18811fe3630321ba79e186aead60e3`

The embedded Task 1 audit payload, Task 2 artifact/model receipt, and Task 3
artifact/result identities remain those bound in
`nix/models.nix`: `7d7a37d08df7e63bdb95063674fe5dc306058e51af8a11bbcd97a4cb2972a766`,
`af1901917b52876a9b3343712b89928b272e5dd237cd491ddd9d462c56a52838`,
`5e56907e60c83c5d98b3c3fe88772b7dfba71e53a9435de548a9d54ea7497834`,
`9e8d080ad6717ad7a2900f6895e36bd95401eb6cb9ca1b3981afa096c31639c3`,
and `c18106f25030ec58dfd3abc5d75d774506aca65b655fc34b284076b1294f8644`.

## Self-review

- Reviewed the complete staged diff and ran `git diff --cached --check`:
  no whitespace errors.
- Confirmed only one implementation route remains; all exploratory plugin
  files and Nix wiring were removed before commit.
- Confirmed the source patch applies cleanly to the exact pinned revision.
- Confirmed the legalization is ordered before the failing pass and matches
  only the exact right-shift spelling.
- Confirmed signed-si64 input/result equality, direct constant requirement,
  closed `[0, 62]` bound, scalar broadcast, registered tensor/tensor rewrite,
  arithmetic `arith.shrsi`, and fail-closed behavior.
- Confirmed no division, rounding helper, narrowing, left shift, adapter, or
  semantic identity change.
- Confirmed `flake.nix` and `nix/pipeline.nix` are unchanged.

## Concerns

The registered stage cannot yet produce its artifact because the authenticated
model also contains `torch.aten.bitwise_left_shift.Tensor_Scalar`. That is a
new compiler frontier outside Task 1's authorized exact-right-shift scope. A
new bounded plan is required before semantic Task 2 can use the full registered
stage. No concern remains for the Task 1 right-shift implementation itself.
