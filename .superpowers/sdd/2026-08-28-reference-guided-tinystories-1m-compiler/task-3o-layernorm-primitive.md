# Supplemental Task 3o report — independent RTL-width LayerNorm primitive

## Result

Implemented `scripts/comparison/tinystories_1m_rtl_layernorm.py`, an
independently written fixed-point primitive for the authenticated
`synthesizable_rtl` LayerNorm profile.  It accepts exactly one 64-lane row of
signed Q16.16 int32 values, gamma, and beta; uses a signed 64-bit mean
accumulator, signed 33-bit deltas, unsigned 66-bit squares, a serial unsigned
72-bit sum, an explicit unsigned 64-bit variance assignment after division and
epsilon addition, floor integer square root, truncation-toward-zero quotient,
Q16.16 affine shift, and signed 32-bit output assignment/wrap.

The generated, self-hashing vector in
`artifacts/reference/tinystories-1m-rtl-layernorm-vector.json` is bound to the
Task 3n LayerNorm receipt SHA-256.  Tests exercise the 66/72-bit overflow
witness, the signed-32 affine wrap witness, exact row shape, vector integrity,
and the explicit integration state.

No package adapter/export integration was made: the current compiler has no
`torch.export`/MLIR lowering bridge that emits this primitive.  The precise
next unsupported operation remains `aten.layer_norm.default` with code
`rtl_layer_norm_compiler_bridge_not_implemented`.  The runtime-vs-RTL conflict
remains unresolved (`runtime_equivalent: false`), and this work has no board
authentication claim.  No reference source or RTL was copied; no PCIe, DDR3,
or transport code changed.

## Files

- `scripts/comparison/tinystories_1m_rtl_layernorm.py`
- `artifacts/reference/tinystories-1m-rtl-layernorm-vector.json`
- `tests/test_tinystories_1m_rtl_layernorm.py`

## Verification

```text
nix develop -c python -m unittest \
  tests/test_tinystories_1m_layernorm_semantics.py \
  tests/test_tinystories_1m_fixed_profile_slice_lowering.py \
  tests/test_tinystories_1m_rtl_layernorm.py -v

Ran 17 tests ... OK
```
