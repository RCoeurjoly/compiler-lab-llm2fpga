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
layout. A further source optimization narrows authenticated 64-bit scale and
parameter words to 32-bit storage with explicit sign-extension adapters. The
current artifact measures 123 logical memories, 1,174 banks, and 43,278,336
physical storage bits. The latest conservative lifetime pass additionally
coalesces the two C/FC code-buffer pairs and attention maximum/denominator;
the current artifact measures 121 logical memories, 1,171 banks, and
43,167,744 physical storage bits. This remains a sizing receipt, not a fit
claim.

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

The bounded no-FSM Yosys checkpoint on the narrowed 16-step SV completed in
15.19 seconds (peak memory 460.59 MiB), producing 11,539 cells and 30 logical
`$mem_v2` cells. This is an elaboration checkpoint only; memory technology
mapping, timing closure, and board execution remain unverified.

A fresh Nix/Yosys `proc; stat` run on the current compiler-emitted
`/tmp/llm2fpga-final-sem3/model.sv` also completed successfully. Before memory
technology mapping it reports 37,500,000 inferred memory bits and 17,217 cells
(591,119 total wire bits). 37.5 Mib is approximately 1,017 ideal RAMB36E1
blocks, already above the 955-block YPCB budget; the physical bank estimate
above is more conservative because it accounts for legal width/depth
geometry. This confirms that the next blocker is physical storage packing and
lifetime reuse, not RTL elaboration.
