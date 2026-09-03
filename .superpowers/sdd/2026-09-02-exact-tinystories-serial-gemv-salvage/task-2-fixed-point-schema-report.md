# Task 2: fixed-point GEMV/requantize schema

Implemented a project-owned, out-of-tree Python schema plugin at
`tools/fixed_point_schema/fixed_point_schema.py`.  It consumes only the
authenticated Task 1 fixture and emits generic MLIR plus a self-hashed schema
receipt; no compiled dialect, CIRCT rebuild, or Calyx path is involved.

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
`8e6339dab7fdd23171645f668ce293bb1e7ecdfc2a60f4f88677b8736af90bc9`.
Its companion `.mlir` is generic operation text, not a new compiled dialect.

The evaluator reconstructs input QDQ, exact serial GEMV, weight rescale, and
output QDQ from fixture values.  It matches the fixture’s accumulator,
requantized-code, and requantized-Q16.16 raw-byte hashes.  Focused TDD tests
cover logical SSA/attributes, missing or altered scale/rounding/signedness/
saturation/width rejection, and output-hash equality.
