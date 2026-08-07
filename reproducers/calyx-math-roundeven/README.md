# Calyx `math.roundeven` Reproducer

This isolates the direct-Linalg no-handshake Calyx `math.roundeven` blocker
that appears after static memref views and `cf.assert` have been lowered.

`circt-opt --lower-scf-to-calyx='top-level-function=main' input.mlir` rejects
`math.roundeven` during Calyx op grouping. The no-handshake pipeline handles
this with the checked-in `llm2fpga-lower-roundeven-for-calyx` MLIR pass, which
lowers scalar `f32` round-to-nearest-even into arith operations before Calyx
lowering. In the RC's exact Q4.12 requantization family, the overflowing
`-FLT_MAX / 2^-12 -> -inf` result bypasses the integer conversion. The guard is
deliberately limited to values below `-FLT_MAX`: finite f32 values remain on
the normal round-to-nearest-even path, while the observed exceptional result
does not wrap through integer arithmetic. `nonfinite.mlir` tracks this masked-
softmax regression.

Textual MLIR substitution is not an acceptable fix.
