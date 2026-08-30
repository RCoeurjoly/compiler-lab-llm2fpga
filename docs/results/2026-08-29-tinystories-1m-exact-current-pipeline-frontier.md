# Exact TinyStories-1M current-pipeline frontier

## Result

The unchanged registered pipeline reaches its first causal invalid stage at
`torch-mlir`, classified as `torch_mlir_frontier`:

```text
loc("/build/exact-adapter-root/TinyStories/model_adapter_exact_package.py":879:0): error: failed to legalize operation 'torch.operator' that was explicitly marked illegal
```

The registered `pytorch-exported` command exited 0. The immediately following
registered `torch` command exited 1 with the compiler diagnostic above. No
Linalg, SCF, flat-SCF, Calyx, or SystemVerilog target was invoked.

## Source and derivation identity

The accepted pipeline base is Task 4 commit
`7eed3592a661c0cb3c417dc59b29839266446b2d`. The final two evidence runs were
executed from distinct descendant commit
`f26177ee480187dd1abf5ee9b1324c61bcceab02`.

Before executing a stage, the generator rejected dirty critical inputs and
compared every critical workspace file to all of:

- its Task 4 Git blob and SHA-256;
- the evidence commit's Git blob;
- the file in the commit-pinned Nix flake source
  (`sha256-ouNdnHwDhw5BlFK16sJL5aAbXgqK6St3MlOiyllKD6w=`);
- its explicit derivation store source when the file is embedded in the export
  or Torch derivation.

This covers `flake.nix`, `flake.lock`, `nix/models.nix`, `nix/pipeline.nix`, the
exact adapter, export/import commands, Task 1--3 receipts, and the exact design
input. The receipt records every file/blob/store hash plus both derivation-file,
canonical derivation-JSON, and build-command hashes.

## Deterministic evidence serialization

Canonical execution fields replace only the run-local compiler capture root
with the explicit placeholder `<capture-tmp>`. Diagnostic locations under
`/build`, exact `/nix/store` tools and inputs, exit codes, and all substantive
output remain unchanged. Canonical logs discard the unrelated Nix dirty-tree
warning and normalize trailing whitespace before hashing. A substantive
diagnostic mutation still changes the hash.

Two fresh full executions from commit `f26177e` were compared, with the first
starting clean and the second starting with the first run's evidence files
dirty. `cmp` found the complete receipt and all three canonical logs
byte-identical:

| Canonical evidence | SHA-256 in both runs |
| --- | --- |
| serialized receipt | `b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55` |
| receipt self-hash | `af3270ff9194b87ca2670f366a220e6a2ada198474f12e5f30a20e62456e7c1b` |
| export invocation log | `993972ee373fbef7b0d334fc180f1277dc9b61698df7c3ed4aaa17a8c63b74e2` |
| Torch invocation log | `1a0867e7081a0e850d2d30048d7e885f157b4d217fea473c789e5d175f485a29` |
| compiler capture log | `f4e06b290a99aa484117a472a360effa2faecad07c2cdc3fa35273349fdcf399` |

The observed wall times were approximately two and three minutes; runtime is
not part of canonical evidence.

Both actual run bundles are retained under
[`tinystories-1m-exact-frontier-determinism`](../../artifacts/comparison/tinystories-1m-exact-frontier-determinism/manifest.json).
Each contains its receipt and three canonical logs. The manifest binds source
commit, commands, exits, file sizes, raw file SHA-256 values, receipt self-hash,
and explicitly noncanonical timestamps/runtime. Independently verify all
bindings and byte comparisons with:

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py
```

## Executed registered builds

```text
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-pytorch-exported
exit 0
result /nix/store/10l4fc5y1rrwyazk2nq6mw800znln97i-tiny-stories-1m-kev-gpt-exact-pytorch-exported

nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
exit 1
```

The export is 69,510,766 bytes with SHA-256
`6c9d2931a18811560f6565e9d313390fb5e0b7b167af39ddc094e19b949ce085`.
The export and Torch derivation JSON hashes are respectively
`2fb13b6f6c3d89598dc1ab00939818524beada3af1cb5fa416dc632d4699eba9`
and `391fc17a7a0236d3939b9207b7a688f8f9c8a1223cba915a888eba332c3c8110`.
The actual invocation logs, exit codes, and hashes are bound in the receipt;
they are not substituted with reads of prior daemon logs.

## Content-bound failure capture and reduction

After the registered Torch failure, a diagnostic capture used the exact
export store output and the exact Torch derivation's Python environment,
Torch-MLIR `PYTHONPATH`, and `/nix/store/...-compile-pytorch.py`. It exited 1
with the same diagnostic and emitted `UnnammedModule.mlir`. Those emitted bytes
were immediately archived with deterministic gzip settings.

| Evidence | SHA-256 |
| --- | --- |
| exported program | `6c9d2931a18811560f6565e9d313390fb5e0b7b167af39ddc094e19b949ce085` |
| compile script | `c668341ae81c944a9f4e092465e47619824532c6397a9f8797a01914747223d8` |
| exact `torch-mlir-opt` | `fde6c18913b26465da9766c9fd2a51e9dc3835491b344ea4ab220735a0f70e6b` |
| emitted IR, 12,121,418 bytes | `a9a663989a35f3d9e2984486db81a82c2aa7bfff421ec56a8558f99a22f52eb0` |
| deterministic gzip archive | `d56ff38d4ec482297adbc19b81e350b14d703bf5d1424b9ede9200d01e23852e` |
| 334-byte reduced IR | `285a40e0ba9dd999fb4155c465889e1b3fa2dc0768716328bc7e4c8898bc4b37` |

The emitted IR contains 1,755 generic `torch.operator` nodes. The minimal
reproducer retains an original
`torch.aten.bitwise_right_shift.Tensor_Scalar` operation with its original
operand/result types. Both full and reduced IR reproduce the diagnostic with
the exact Torch-MLIR binary and pass pipeline. The available `mlir-reduce` is
LLVM/MLIR 21 and cannot register this LLVM 23 Torch dialect, so the reduction
remains a manually minimized, exact-interestingness-verified operation.

## Command resolution and scope

The brief's `...-torch-mlir` attribute is absent; the model registry names that
logical artifact stage `...-torch`. The missing-alias diagnostic and resolution
are preserved in the machine receipt. This does not change the causal stage:
the registered `...-torch` derivation entered Torch-MLIR and failed in its pass
pipeline.

No partial Torch output was accepted. No backend, model, quantization, DDR,
PCIe, lowering, scheduling, or RTL change was made. No downstream functional,
resource, timing, or board claim is made.
