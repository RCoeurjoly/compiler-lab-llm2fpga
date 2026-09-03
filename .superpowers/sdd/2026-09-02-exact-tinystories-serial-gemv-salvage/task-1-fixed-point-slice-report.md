# Task 1: fixed-point GEMV/requantize fixture

Captured and replayed the first block-0 q-projection boundary for the frozen
TinyStories-1M prompt `[7454, 2402, 257, 640]`.

The self-hashed fixture is
`artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json`.
It binds the exact contract, package manifest/weights/scales/receipt, model
config, adapter/capture sources, and immutable successor-generation receipt.

Recorded tensors are all real `4 x 64` eager values:

- input activation dequantized Q16.16;
- exact signed-i64 wrapped GEMV accumulator;
- requantized signed-int8 output codes; and
- requantized/dequantized Q16.16 output.

The fixture receipt SHA-256 is
`b765eafb953076ada9cf925b04ae21035ba6bac0fabda264cbb1279bea09cf3e`.
The deterministic eager replay test rebuilds the authenticated model through
the successor-authorized loader and compares every bound tensor and identity.

Verification: the intentional missing-fixture test was red, then
`timeout 1800 nix develop -c python -m unittest
tests/test_tinystories_1m_fixed_point_gemv_requantize_slice.py -v` passed.
No compiler pass or Calyx code was changed.
