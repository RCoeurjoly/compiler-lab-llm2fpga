# Task 3 Main Pipeline Port

This directory starts from `RCoeurjoly/LLM2FPGA` commit `b6dc8ab` on `main`,
including that revision's `flake.lock`. The representative-core additions are
limited to its model adapter, generated selftest wrapper, utilization package,
and non-gating FTS comparison report.

The root project imports this directory as a flake so FTS and RC share this
exact closure independently of the root project's newer lowering toolchain.
