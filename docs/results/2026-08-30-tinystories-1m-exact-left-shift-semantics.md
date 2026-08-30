# Exact TinyStories-1M signed left-shift semantics

## Result

`torch.aten.bitwise_left_shift.Tensor_Scalar` is frozen here as a signed
`si64` tensor with a compile-time scalar count in the closed interval `0..62`.
The fixture was observed with pinned PyTorch 2.9.1 and is independently checked
as two's-complement 64-bit arithmetic: mask the input to 64 bits, left shift,
mask again, then reinterpret bit 63 as the sign bit.

The six live-PyTorch cases are: identity at count 0; the actual successor
reproducer's `[4,64]` shape and count 16; a negative operand; positive
high-bit sign wrapping; negative high-bit discard; and count 62. Every valid
case records decimal output values, `si64` dtype, and the input shape.

The four non-executed cases are compiler-contract rejections, not claims about
PyTorch rejection:

| Case | Contract status | Diagnostic |
| --- | --- | --- |
| negative count | `rejected_negative_shift` | `shift_contract:negative_shift` |
| count 63 | `rejected_shift_greater_than_sixty_two` | `shift_contract:greater_than_sixty_two` |
| dynamic count | `rejected_dynamic_shift` | `shift_contract:dynamic_shift` |
| `si32` tensor | `rejected_unsupported_dtype` | `shift_contract:unsupported_dtype` |

In particular, count 63 is outside the supported compiler domain even though a
live PyTorch invocation may produce a value.

## Authenticated fixture

[`tinystories-1m-exact-left-shift-semantics.json`](../../artifacts/comparison/tinystories-1m-exact-left-shift-semantics.json)
is canonical JSON with payload self-hash
`672d34819f93db399e7e8faac4747f9bb88b690491c2683912fee9490ffca19c`.
It binds the exact adapter, the left-shift reproducer, the accepted successor
receipt, and the existing Task 1--3 identities. It also binds the pinned
PyTorch module path, version, and module-file SHA-256 used for execution.

The verifier rechecks all file and receipt identities, recomputes each valid
case independently, then calls live pinned `torch.bitwise_left_shift` and
requires identical dtype, shape, and values:

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py
nix develop -c python -m unittest tests/test_tinystories_1m_exact_left_shift_semantics.py -v
```

No compiler, patch, pipeline, model, or RTL source is modified by this task.
