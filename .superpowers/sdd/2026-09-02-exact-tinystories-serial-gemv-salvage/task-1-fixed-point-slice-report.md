# Task 1: fixed-point GEMV/requantize fixture

Captured and replayed the first block-0 q-projection boundary for the frozen
TinyStories-1M prompt `[7454, 2402, 257, 640]`.

The self-hashed fixture is
`artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json`.
It binds the exact contract, package manifest/weights/scales/receipt, model
config, adapter/capture sources, and immutable successor-generation receipt.

Recorded tensors are real eager values, with every value-list, raw little-endian
int64 byte count, and raw-byte SHA-256 independently validated:

- input activation signed-int8 QDQ codes and per-channel Q8.24 scale;
- input activation dequantized Q16.16;
- authenticated q-projection signed-int8 weight codes and per-output Q8.24
  scales;
- exact signed-i64 wrapped GEMV accumulator;
- output per-channel Q8.24 scale and requantized signed-int8 codes; and
- requantized/dequantized Q16.16 output.

The fixture receipt SHA-256 is
`d30d469ecc0c7a679c097577affd12afe9cb2fc250a252caeaba141cdeb55771`.
The deterministic eager replay test rebuilds the authenticated model through
the successor-authorized loader and compares every bound tensor and identity.
A separate fixed-point replay rebuilds QDQ, the exact GEMV accumulator, and
the output requantization from the captured codes/scales without model access.

Verification: the intentional missing-fixture test was red, then
`timeout 1800 nix develop -c python -m unittest
tests/test_tinystories_1m_fixed_point_gemv_requantize_slice.py -v` passed.
No compiler pass or Calyx code was changed.
