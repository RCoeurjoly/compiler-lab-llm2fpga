# Task 5 report: exact current-pipeline frontier

## Status

Verified after fix round 1. The accepted pipeline base is
`7eed3592a661c0cb3c417dc59b29839266446b2d`; the final deterministic evidence
source is its distinct descendant
`f26177ee480187dd1abf5ee9b1324c61bcceab02`.

The earliest causal invalid stage is `torch-mlir`, classified as
`torch_mlir_frontier`. Its exact registered-build diagnostic is:

```text
loc("/build/exact-adapter-root/TinyStories/model_adapter_exact_package.py":879:0): error: failed to legalize operation 'torch.operator' that was explicitly marked illegal
```

The smallest verified original operation is
`torch.aten.bitwise_right_shift.Tensor_Scalar`. Linalg and all later stages were
not run.

## Fix-round deliverables

- The classifier opens and hashes the actual log and parses compiler/unhandled
  diagnostics itself. Caller-supplied diagnostics cannot substitute for log
  evidence. A zero-exit Calyx `Unhandled operation` is invalid.
- Stage evidence must be a contiguous prefix of the canonical order beginning
  at `pytorch-exported`, ending exactly at the first invalid stage. A successful
  prefix is complete only if it contains every canonical stage.
- The generator proves Task 4 ancestry and rejects dirty or Task-4-mutated
  critical pipeline inputs. It binds workspace, Git blob, flake archive,
  explicit derivation source, derivation file/JSON, and builder-command hashes.
- The generator actually invoked both registered build commands in this run.
  It stopped after the Torch failure and did not read a prior daemon log as a
  substitute for execution.
- A separate exact import capture used the evaluated Torch derivation's export,
  Python, compile script, Torch-MLIR environment, binary, and pass pipeline. The
  archived full IR is the deterministic gzip of bytes emitted by that capture.
- Full and minimal IR reproduce the diagnostic under the exact tool. The
  minimal operation retains the original name and types. Automated
  `mlir-reduce` remains unsupported because the packaged reducer is MLIR 21 and
  the Torch dialect/tool is LLVM 23.
- Run-local capture roots are normalized to `<capture-tmp>` in canonical
  command/log fields. Exact store/tool paths and diagnostic locations are
  retained. The flake archive is pinned to the evidence commit rather than the
  dirty worktree.

## Executed commands and results

```text
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-pytorch-exported
exit 0

nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
exit 1

<exact derivation Python> <exact /nix/store/...-compile-pytorch.py> \
  --exported-program-dir <exact export store output> --out <capture temp>/requested-torch.mlir
exit 1
```

The exact capture command, temporary path, output/error log, environment-bound
tool paths, and hashes are recorded in the machine receipt. The focused suite
passes 24 tests under `nix develop`.

Two final fresh executions from `f26177e` produced byte-identical receipt JSON
and byte-identical export, Torch, and capture logs. Run 1 started clean; run 2
started with run 1's evidence files dirty. The observed runtimes were about two
and three minutes and are deliberately not canonicalized into the receipt.

## Principal identities

| Item | SHA-256 |
| --- | --- |
| serialized receipt | `b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55` |
| receipt self-hash | `af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b` |
| flake archive NAR | `sha256-ouNdnHwDhw5BlFK16sJL5aAbXgqK6St3MlOiyllKD6w=` |
| export canonical log | `993972ee373fbef7b0d334fc180f1277dc9b61698df7c3ed4aaa17a8c63b74e2` |
| Torch canonical log | `1a0867e7081a0e850d2d30048d7e885f157b4d217fea473c789e5d175f485a29` |
| capture canonical log | `f4e06b290a99aa484117a472a360effa2faecad07c2cdc3fa35273349fdcf399` |
| export derivation JSON | `2fb13b6f6c3d89598dc1ab00939818524beada3af1cb5fa416dc632d4699eba9` |
| Torch derivation JSON | `391fc17a7a0236d3939b9207b7a688f8f9c8a1223cba915a888eba332c3c8110` |
| `exported.pt2` | `6c9d2931a18811560f6565e9d313390fb5e0b7b167af39ddc094e19b949ce085` |
| emitted failing IR | `a9a663989a35f3d9e2984486db81a82c2aa7bfff421ec56a8558f99a22f52eb0` |
| deterministic IR archive | `d56ff38d4ec482297adbc19b81e350b14d703bf5d1424b9ede9200d01e23852e` |
| reduced IR | `285a40e0ba9dd999fb4155c465889e1b3fa2dc0768716328bc7e4c8898bc4b37` |
| compile script | `c668341ae81c944a9f4e092465e47619824532c6397a9f8797a01914747223d8` |
| exact `torch-mlir-opt` | `fde6c18913b26465da9766c9fd2a51e9dc3835491b344ea4ab220735a0f70e6b` |

## Scope and concern

No backend, model, quantization, DDR, PCIe, lowering, scheduling, or RTL change
was made. The brief's `...-torch-mlir` alias is absent; the registered logical
Torch-MLIR artifact suffix is `...-torch`, and that actual derivation was
executed. A future compiler task must legalize the exact integer tensor shift
before any claim about Linalg or later stages.
