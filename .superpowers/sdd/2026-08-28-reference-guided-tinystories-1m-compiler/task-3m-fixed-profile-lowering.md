# Supplemental Task 3m report — fixed-profile one-block lowering

## Result

The full one-block lowering cannot yet be implemented faithfully.  The new
probe binds the exact Task 3l contract, profile, Q/DQ receipt, adapter receipt,
package receipt, numeric trace, and exported PT2 archive before loading the
graph.  It inspected the actual 394-operation `torch.export` graph and found
the first transformer-block operation at graph index 149:
`aten.layer_norm.default` (`block.ln_1`).

The authenticated profile defines activation Q/DQ and GEMV arithmetic but has
no executable LayerNorm specification.  In particular, mean/variance
reduction order and width, epsilon, inverse square root, and gamma/beta
rounding/overflow are absent.  The two LayerNorm checkpoints cannot be used as
a general operator definition.  The result therefore fails closed with
`fixed_layer_norm_semantics_unavailable` and emits no MLIR, SV, RTLIL, or
simulation-equivalence claim.  The 12-checkpoint profile trace is hash
validated, not rerun or misrepresented as compiler output.  Board authority
remains unresolved.

## Files

- `scripts/comparison/lower_tinystories_1m_fixed_profile_slice.py`
- `tests/test_tinystories_1m_fixed_profile_slice_lowering.py`
- `artifacts/comparison/tinystories-1m-fixed-profile-slice-lowering.json`
- `docs/results/2026-08-29-tinystories-1m-fixed-profile-slice-lowering.md`

## TDD and verification

The focused suite was first run before the implementation existed and failed
with `FileNotFoundError` for the new lowering probe.  After implementation:

```text
XDG_CACHE_HOME=/tmp/codex-task3m-nix-cache nix develop -c python -m unittest \
  tests.test_tinystories_1m_fixed_profile_slice_lowering -v

Ran 5 tests in 1.744s
OK
```

The tests include a real generated PT2 LayerNorm archive, the canonical Task
3l full export, wrong-export rejection before deserialization, precise first
unsupported-op classification, and prevention of partial compiler-artifact or
equivalence claims.

No transport, DDR3, PCIe, board, frozen model, reference source, or reference
RTL was changed.
