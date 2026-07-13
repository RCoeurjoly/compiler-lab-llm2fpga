# ADR: Fast compiler iteration ends at RTLIL

- Status: accepted
- Date: 2026-07-10

## Context

The representative core (RC) is only about four times faster to iterate than
full TinyStories (FTS), despite using a vocabulary of 32 instead of 50,257 and
minimum model dimensions. The existing Task 3 flow continues past lowering
through nine Yosys synthesis stages and deferred FPGA-oriented processing.
Those stages introduce a substantial fixed cost that model shrinking cannot
remove.

## Decision

Use two workflows:

1. The fast compiler loop runs from the model/frontend through MLIR and Calyx
   to RTLIL. RTLIL is the success boundary and should include diagnostics and
   lightweight artifact-size statistics.
2. Full Yosys technology mapping and Xilinx synthesis remain deferred
   validation runs for selected checkpoints.

The fast loop should be exposed as a reusable, cacheable pipeline rather than
requiring the full synthesis package to be built first.

## Consequences

Compiler and lowering changes can receive hardware-relevant feedback without
waiting for FPGA synthesis. Full resource-utilization conclusions still
require the deferred validation workflow. The fast path must make its cache
keys and invalidation boundaries explicit so stale RTLIL cannot hide a
frontend or lowering change.

## Packaging direction

Expose the fast workflow as a dedicated flake package surface alongside the
existing full pipeline. Provide independently cacheable MLIR, Calyx, and RTLIL
checkpoints, with the RTLIL package as the normal fast-loop target.
