# TinyStories-1M compiler BRAM budget checkpoint

The compiler now publishes a legal RAMB36E1 geometry for each logical memory
(`runtime_bram_bank_plan`).  Generating the authenticated 16-step production
artifact and summing the required physical banks gives:

* 114 logical memories;
* 1,216 RAMB36-equivalent banks;
* 44,826,624 physical storage bits.

The YPCB budget used by this project is 955 RAMB36E1 blocks.  Therefore a
literal bank-per-logical-memory implementation cannot fit; it is a sizing
receipt, not a fit claim.  The next compiler pass must preserve the logical
memory ABI while reusing or packing storage (especially shared weights and
scratch buffers), then re-run this calculation from the transformed artifact.

The calculation was run in the project Nix environment:

```text
nix develop -c python ... generate_production_kernel(..., generation_steps=16)
```

Simulation remains on the unchanged logical `seq_mem_d1` representation until
the physical-memory lowering is implemented and its preload metadata is updated
together with the generated RTL.
