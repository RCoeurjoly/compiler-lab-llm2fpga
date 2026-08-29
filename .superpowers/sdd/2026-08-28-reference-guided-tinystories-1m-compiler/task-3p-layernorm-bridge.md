# Supplemental Task 3p report — fixed LayerNorm compiler bridge

## Result

The canonical package-adapter export now has an explicit compiler-side bridge
for graph index 149, `aten.layer_norm.default`.  The bridge accepts only the
authenticated block-0 `ln_1` operation with source shape `[1,4,64]`, float32
source gamma/beta parameters of shape `[64]`, default epsilon `1e-5`, and
token index 3.  It emits one deterministic, parseable custom MLIR operation,
`llm2fpga.fixed_layer_norm_q16_16`, over three `tensor<64xi32>` operands.

The custom-op attributes preserve the Task 3o Q16.16 ports, signed-64 mean,
33-bit deltas, 66-bit squares, ascending-index 72-bit variance sum, unsigned
64-bit variance assignment, epsilon 42950 in Q32.32, floor integer square
root, truncation-toward-zero division, affine shift, and signed-32 wrap.  Its
evidence binds the Task 3n profile, Task 3o vector and independent primitive,
the fixed Q/DQ profile, package adapter, and all twelve ordered checkpoint
hashes.  Re-executing the Task 3o vector through the bridge primitive produces
the exact recorded result hash.

Each public stage independently revalidates those identities.  The bridge
rejects non-canonical graph indices/names, missing adapter/export hashes,
boolean or otherwise non-integer shapes, forged profile/QDQ/adapter hashes,
changed or reordered checkpoint hashes, and altered numeric trace hashes.  The
lowering hook repeats source, evidence, descriptor, and checkpoint validation;
the report additionally requires byte-exact MLIR regeneration.  The MLIR
module manifest carries the source/export identities, arithmetic and numeric
trace identities, and every ordered checkpoint name/hash.  The deterministic
bridge evidence receipt itself is pinned to SHA-256 `83ee250e39f65e2484c4bf918bccf60d3de7c38e8c74b786766ad5c33cac5bda`;
rehashed substitutions are rejected by both lowering and report generation.

The precise next unsupported boundary is
`fixed_layer_norm_backend_lowering_not_implemented`: the existing
Linalg/Calyx backend does not legalize the new custom op.  The checked-in
receipt therefore remains `unsupported` / `unaligned`; it emits no
SystemVerilog or RTLIL and makes no runtime-, board-, timing-, or inference-
equivalence claim.  No reference source or RTL was copied and no transport
code changed.

## Files

- `scripts/comparison/bridge_tinystories_1m_rtl_layernorm.py`
- `scripts/comparison/tinystories_1m_rtl_layernorm.py`
- `tests/test_tinystories_1m_rtl_layernorm_bridge.py`
- `tests/test_tinystories_1m_rtl_layernorm.py`
- `artifacts/comparison/tinystories-1m-fixed-layernorm-bridge.mlir`
- `artifacts/comparison/tinystories-1m-fixed-layernorm-bridge.json`

## Verification

The pinned Nix test command covers the original primitive, semantics/profile
handoff, old lowering gate, new strict bridge, canonical PT2 inspection,
tamper rejection, deterministic IR, and exact numeric trace.  The emitted IR
is also parsed with CIRCT using `--allow-unregistered-dialect`; legalization is
intentionally absent and remains the reported boundary.

```text
nix develop -c python -m unittest \
  tests/test_tinystories_1m_package_adapter.py \
  tests/test_tinystories_1m_layernorm_semantics.py \
  tests/test_tinystories_1m_fixed_profile_slice_lowering.py \
  tests/test_tinystories_1m_rtl_layernorm.py \
  tests/test_tinystories_1m_rtl_layernorm_bridge.py -v

Ran 38 tests ... OK

nix develop -c circt-opt --allow-unregistered-dialect \
  artifacts/comparison/tinystories-1m-fixed-layernorm-bridge.mlir

exit 0
```
