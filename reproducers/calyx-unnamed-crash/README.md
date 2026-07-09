# Calyx Dense Resource Crash Reproducer

This captures the pre-Calyx IR for the fixed-layernorm representative-core
direct-Linalg no-handshake path after model simplifications removed `math.rsqrt`,
`math.exp`, `math.fpowi`, and `math.tanh`.

Before `llm2fpga-lower-static-memref-views-for-calyx` materialized f32
`DenseResourceElementsAttr` globals into ordinary dense globals, CIRCT
`--lower-scf-to-calyx` segfaulted in `DenseElementsAttr::getNumElements`.

The compiler-pipeline fix is in the checked-in MLIR pass plugin. Textual MLIR
rewriting is not an acceptable fix.
