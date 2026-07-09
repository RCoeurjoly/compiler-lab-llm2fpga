# Calyx `math.rsqrt` Reproducer

This isolates the direct-Linalg no-handshake Calyx blocker that appears after
`math.roundeven` is lowered by `llm2fpga-lower-roundeven-for-calyx`.

The representative-core flat-SCF has scalar `math.rsqrt` operations in
normalization-like variance paths. `circt-opt --lower-scf-to-calyx` rejects the
operation during Calyx op grouping. Acceptable fixes are to choose a frontend or
dialect path that represents normalization in supported integer/fixed-point
operations, use an official MLIR/CIRCT lowering for reciprocal square root, or
add an actual MLIR pass with a documented numerical contract.

Textual MLIR substitution is not an acceptable fix.
