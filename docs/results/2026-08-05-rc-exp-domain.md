# RC exponential-domain gate

The existing exhaustive enumerator was started for all `6^8 = 1,679,616`
contexts; the cached reproducible pilot receipt is retained as the current
evidence while the exhaustive derivation remains unavailable in this host
session. The pilot covers four contexts and 256 values at each of two softmax
sites.

- Source model: `tinystories-w8a8-rc-study-mask9-vocab6-width2`
- Export SHA-256: `60af40afb1a860ed97e6a14dd4b10f08c79f5cbcbe4719025ea023d43f2d9375`
- Both sites: `torch.float32` pre-exp operand, softmax dimension `-1`
- Observed finite range: `[-0.0009765625, 0.0]`
- Positive, NaN, and infinity counts: zero
- Quantization scale: `2^-12`; zero point `-124`; int8 range `[-128, 127]`
- Pilot semantic repeat: identical (`semantic_determinism: true`)

For the table gate, one input quantization bin is added below the observed
minimum, producing the conservative generation interval `[-0.001220703125,
0.0]`. The exhaustive receipt must replace this pilot evidence before calling
the interval complete for all lexical contexts.

The raw pilot receipt is [available in the derivation output](../../artifacts/rc_exp_domain_pilot.json)
when materialized locally; the table generator records its own source hash.
