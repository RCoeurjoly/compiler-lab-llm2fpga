# Task 2: fixed-point GEMV/requantize schema

Implemented a project-owned, out-of-tree Python schema plugin at
`tools/fixed_point_schema/fixed_point_schema.py`.  Its registered pass name is
`llm2fpga-fixed-point-gemv-requantize-schema`; it consumes incoming generic
MLIR plus the authenticated Task 1 fixture and emits generic MLIR and a
self-hashed schema receipt.  No compiled dialect, CIRCT rebuild, or Calyx path
is involved.

The generic MLIR uses logical SSA values for activation, input scale, weight,
weight scale, accumulator, and requantized result.  The `fixed.requantize`
operation binds the exact output-scale identity and explicit attributes:

- per-channel unsigned Q8.24 scale;
- nearest-ties-away-from-zero rounding;
- signed output;
- `[-128, 127]` saturation; and
- width 8.

`artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-schema.json`
has receipt SHA-256
`d276a23dc80cb6c9db978d16a4f348bde816ded149c02b8cab7e4a2364397d76`.
Its companion `.mlir` is generic operation text, not a new compiled dialect.

The evaluator reconstructs input QDQ, exact serial GEMV, weight rescale, and
output QDQ from fixture values.  It matches the fixture’s accumulator,
requantized-code, and requantized-Q16.16 raw-byte hashes.  Focused TDD tests
cover logical SSA/attributes, missing or altered scale/rounding/signedness/
saturation/width rejection, forged MLIR attribute/scale-operand rejection,
wrong incoming-MLIR rejection, and output-hash equality.  The verifier parses
the emitted generic MLIR and recomputes its contract-hash attribute; it also
binds and verifies every Task 1 raw code/scale/weight/accumulator/output hash.

Repair round 2 replaces the former textual matching with a structural parser
for the supported one-line generic-MLIR subset.  It follows
`fixed.requantize(%acc, %output_scale)` to its defining operations and requires
each fixture producer—activation, input scale, weights, weight scale, and
output scale—to carry the immutable Task 1 receipt SHA-256, tensor name, raw
little-endian SHA-256, and raw byte count.  The authoritative raw payloads
remain in that self-hashed Task 1 fixture, so these values bind the emitted
SSA producers to both fixture identity and payload.  Regression tests recompute
the outer schema receipt hash after a forged defining-operation or operand
substitution; structural provenance validation still rejects it.
