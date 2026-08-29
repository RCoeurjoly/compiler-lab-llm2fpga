# Supplemental Task 3k report: authenticated package lowering gate

## Result

Added the Nix application/package
`tinystories-1m-authenticated-package-lowering`.  It materializes the reviewed
Task 3f authenticated GPT-Neo `ExportedProgram` using the pinned Nix Python
environment, then passes its canonical receipt, numeric trace, and package
receipt through a fail-closed compiler-entry gate.

The run is intentionally **unsupported**, not lowered or aligned.  The
authenticated adapter receipt proves that all 97 activation boundaries exist,
but also proves `activation_qdq_execution` is `metadata_only` with reason
`activation_rounding_semantics_unavailable`.  Rounding, saturation, and clamp
rules are therefore absent.  Calling the existing FP32 compiler on the
reconstructed logits export would drop required semantics and create an
invalid alignment claim.  The gate records that as the first reproducible
lowering failure before any FP32 lowering can begin.

## Command

```text
nix run .#tinystories-1m-authenticated-package-lowering -- \
  --package /home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m \
  --out-dir /tmp/tinystories-1m-authenticated-package-lowering-check
```

The output preserves `canonical-contract.json`, `adapter-receipt.json`,
`package-receipt.json`, `exported.pt2`, and `numeric-trace.json`, plus
`lowering-attempt.json` and `compiler-artifact-metadata.json`.  The metadata
contains the exact Task 2 `contract_identity` but no invented RTL/SV/RTLIL
source path or hash, so the strict extractor cannot treat it as a ready slice.

Observed output fields:

```text
status: unsupported
alignment_status: unaligned
activation_qdq_boundary_count: 97
failure.code: activation_rounding_semantics_unavailable
compiler_artifact: null
```

## Verification

```text
nix develop -c python -m unittest -v \
  tests.test_tinystories_1m_authenticated_package_lowering
nix build .#tinystories-1m-authenticated-package-lowering --no-link -L
nix run .#tinystories-1m-authenticated-package-lowering -- ...
```

The focused suite passes three tests: receipt/QDQ preservation and honest
unsupported status, tampered exported-program rejection, and the Nix entry
point's non-RC/non-transport scope.  The final command materialized the full
authenticated export and generated the verified unsupported receipt.

## Scope

No RTL, compiler optimization, Representative Core, PCIe, DDR3, transport, or
weight file was changed.  No hardware or optimization success is claimed.
