# Calyx `math.roundeven` Reproducer

This isolates the direct-Linalg no-handshake Calyx `math.roundeven` blocker
that appears after static memref views and `cf.assert` have been lowered.

`circt-opt --lower-scf-to-calyx='top-level-function=main' input.mlir` rejects
`math.roundeven` during Calyx op grouping. The no-handshake pipeline handles
this with the checked-in `llm2fpga-lower-roundeven-for-calyx` MLIR pass, which
lowers scalar `f32` round-to-nearest-even into arith operations before Calyx
lowering. The pass is intended for finite values in the `i32` range, matching
the quantization pattern that later clamps and converts to integer.

Textual MLIR substitution is not an acceptable fix.
