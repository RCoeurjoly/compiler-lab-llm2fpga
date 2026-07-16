# Quantized RC Nonlinear Lowering Frontier

**Status:** `blocked-standard-route-frontier`

## Fixed unit and oracle

- Model key: `tinystories-w8a8-rc-study-mask9-vocab6-width2`.
- Frozen corpus cases: `ascending`, `descending`, `zeros`, `alternating`
- The comparison boundary is six final raw int8 codes plus the lowest-index argmax token ID for every frozen case.

## Inputs and tool provenance

- `flat_scf`: SHA-256 `2a2d0f15794833cb8af0fcdf168aef863e337f034750f7764c24da828d1525b1`, path `/nix/store/qs0hxppzszk1kq6fr1sdzfn8sghgsixb-tinystories-w8a8-rc-study-mask9-vocab6-width2-flat-scf/flat.scf.mlir`.
- `reference`: SHA-256 `9d5523b25495011ab1ad495eb1d1e1a263bd98a093b3449fbdd2b39b3000de98`, path `/nix/store/cfdf57zdzim87npwdvn68i9ldhq3yx81-tinystories-w8a8-rc-reference-image/reference.json`.
- `slices`: SHA-256 `130c19a9b837c8d2d5010d734704698255e02d9411b7c271b5105cc391b075d2`, path `/nix/store/dvaqdgcmlifsg8yv1x0n1miybv1g4s9j-tinystories-w8a8-rc-nonlinear-slices/slices.json`.
- `torch_mlir`: SHA-256 `0437be0a227396daaa88b78f7f42335f6a1db21e30538a6e5c5e726fc5490c13`, path `/nix/store/b585f6lb2054qiqff4j82xc17jmlx7hd-tinystories-w8a8-rc-study-mask9-vocab6-width2-torch.mlir`.
- `circt_opt`: `/nix/store/6nz8q4n4z2c3yb6xikq84rbn1rrh61xy-circt-1.144.0g20260331_5dc62fe/bin/circt-opt` (exit `0`).
- `mlir_opt`: `/nix/store/kzsmdvqsd6y5qd6wsaxdys526s2j9f1m-mlir-23.0.0-unstable-2026-01-20/bin/mlir-opt` (exit `0`).
- `torch_mlir_opt`: `/nix/store/swlkp7wlw75vv2i3l2f1dh8phnd33jqv-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt` (exit `0`).

## Nonlinear family evidence

| Family | Source operation | Route results | Representation | CIRCT | Oracle comparison | Route documentation |
| --- | --- | --- | --- | --- | --- | --- |
| exp | math.exp | direct-circt; upstream-canonicalize-cse; upstream-convert-math-to-funcs; upstream-convert-math-to-libm | float; unknown | rejected | not-run | circt-scf-to-calyx; mlir-canonicalize-and-math |
| tanh | math.tanh | direct-circt; upstream-canonicalize-cse; upstream-convert-math-to-funcs; upstream-convert-math-to-libm | float; unknown | rejected | not-run | circt-scf-to-calyx; mlir-canonicalize-and-math |
| fpowi-cube | math.fpowi | direct-circt; upstream-canonicalize-cse; upstream-convert-math-to-funcs; upstream-convert-math-to-libm | float | rejected; skipped | not-run | circt-scf-to-calyx; mlir-canonicalize-and-math |
| sqrt | math.sqrt | direct-circt; upstream-canonicalize-cse; upstream-convert-math-to-funcs; upstream-convert-math-to-libm | float; unknown | accepted; rejected | not-run | circt-scf-to-calyx; mlir-canonicalize-and-math |

## First remaining frontier

- Operation: `math.exp`.
- Route: `direct-circt`.
- Boundary: named standard route did not produce a valid Calyx-accepted artifact

## Recommendation

- Kind: `upstream-compiler-or-hardware-work`.
- Reason: math.exp remains at the first named standard-route boundary; no approximation is implied by this result

## Explicit limits

- Provenance fragments are not numerical equivalence evidence and are not executable semantic replacements.
- No SV, DDR3, host, board, or FPGA-utilization claim is made by this result.
- No approximation, resource-scout transform, or changed PyTorch oracle is used by this result.
