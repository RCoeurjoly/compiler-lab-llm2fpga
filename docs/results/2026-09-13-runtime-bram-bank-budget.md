# TinyStories-1M compiler BRAM budget checkpoint

The compiler now publishes a legal RAMB36E1 geometry for each logical memory
(`runtime_bram_bank_plan`).  Generating the authenticated 16-step production
artifact and summing the required physical banks gives 114 logical memories,
1,216 RAMB36-equivalent banks, and 44,826,624 physical storage bits before
lifetime reuse. The first explicit compiler reuse pass coalesces the serial
Q/K/V/out projection accumulators; the current 16-step artifact measures 110
logical memories, 1,204 banks, and 44,384,256 physical storage bits. A second
explicit reuse class coalesces the serial INT8 projection-code buffers, and a
third repacks token-scale rows into 2,048-word banks. The latest artifact
measures 123 logical memories, 1,182 banks, and 43,573,248 physical storage
bits; the increase in logical-memory count is the intentional 25-bank scale
layout. The immutable source portion is 1,008 banks, so further packing is
still required even before runtime scratch storage is counted.

The YPCB budget used by this project is 955 RAMB36E1 blocks.  Therefore a
literal bank-per-logical-memory implementation still cannot fit; this is a
sizing receipt, not a fit claim. The next compiler pass must preserve the
logical memory ABI while reusing or packing additional storage (especially
shared weights and scratch buffers), then re-run this calculation from the
transformed artifact.

The calculation was run in the project Nix environment:

```text
nix develop -c python ... generate_production_kernel(..., generation_steps=16)
```

Simulation remains on the unchanged logical `seq_mem_d1` representation until
the physical-memory lowering is implemented and its preload metadata is updated
together with the generated RTL.
