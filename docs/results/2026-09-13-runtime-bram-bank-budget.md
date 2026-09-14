# TinyStories-1M compiler BRAM budget checkpoint

## Alias candidate implementation checkpoint (2026-09-14)

The compiler-emitted alias candidate completed the frozen 16-token continuation
for two independent simulation runs. Both produced exactly:

```text
11, 612, 373, 257, 1310, 2576, 3706, 20037,
13, 1375, 6151, 284, 711, 2354, 287, 262
```

Its production receipt reports `status=passed`, `generation_steps=16`, and
authenticated oracle, Futil, and generated-SV hashes. No handwritten or
kev-gpt RTL is used. Nix/Yosys `synth_xilinx -family xc7` also completed and
inferred 1,118 `RAMB36E1` and 322 `DSP48E1` cells. This is not a fit or timing
result: 1,118 RAMB36E1 still exceeds the 955-block YPCB budget by 163.

## Capacity lower-bound analysis

The authenticated alias artifact's 120 memories contain 37,138,432 logical
bits, an ideal lower bound of 1,008 RAMB36E1 blocks before port/geometry
constraints. Immutable weight memories account for 31,899,648 bits (866 ideal
blocks), leaving only 89 blocks under the 955-block device budget. The
remaining runtime memories contain 5,238,784 bits (141 ideal blocks), even
before physical width/depth padding. Therefore bank-geometry tweaks alone
cannot close the gap. The compiler must reduce the simultaneously resident
runtime working set—e.g. tile context rows and prove lifetime reuse—or move
state out of BRAM; changing transport or the arithmetic contract would not
address this bound.

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

## Alias candidate simulation checkpoint (2026-09-14)

The compiler-emitted alias candidate in `/tmp/llm2fpga-alias-full` completed
the frozen 16-token continuation for two independent simulation runs. Both
runs produced exactly:

```text
11, 612, 373, 257, 1310, 2576, 3706, 20037,
13, 1375, 6151, 284, 711, 2354, 287, 262
```

The production receipt reports `status=passed`, `generation_steps=16`, and
records the authenticated oracle, Futil, and generated-SV hashes. No
handwritten or kev-gpt RTL is used. A fresh Nix/Yosys check on the same
generated SV completed successfully, reporting 17,081 cells and 589,975
total wire bits after elaboration. This is not a device-fit or timing result:
the physical BRAM estimate remains 1,171 RAMB36E1-equivalent banks versus the
955-block YPCB budget.

The existing eight-row geometry was also exercised as a bounded gate using the
compiler-generated SV and the Nix-built Verilator harness. Two independent
cold simulations both selected token `11` at cycle `92,936,273` and completed
at cycle `92,936,279`. This validates the four-token prompt/one-token path at
the candidate tile capacity; it does not yet validate contexts longer than the
tile or establish a hardware fit.

Scaling the row-dependent runtime buffers in the authenticated plan gives a
useful design target: a tile capacity of 8 rows has a 33,820,672-bit logical
footprint (918 ideal RAMB36E1 blocks), while capacities 12, 16, and 20 require
937, 957, and 977 ideal blocks respectively. Thus the compiler's next
architectural experiment should stream the real context through 8-row tiles
and use a packed physical allocator; merely reducing the existing 20-row
array or changing bank geometry is insufficient to establish fit.

Xilinx-specific Yosys synthesis of that same eight-row artifact completed
successfully and inferred 1,020 `RAMB36E1` and 322 `DSP48E1` cells. It is 65
RAMB36E1 above the 955-block budget, showing that a packed allocator might
close the initial tile, but this is only the one-token artifact and does not
establish full 16-token multi-tile feasibility.

As a diagnostic-only tradeoff, a temporary synthesis fixture forced the
non-weight runtime buffers to Xilinx distributed RAM. The same eight-row
artifact then inferred 968 `RAMB36E1`, 20,412 `LUT6`, and 322 `DSP48E1` cells.
This is 13 BRAM blocks over budget and therefore not yet a deliverable (the
objective remains BRAM-only), but it confirms that runtime storage—not the
immutable token tables alone—is the actionable pressure point. A valid
solution must either pack those remaining BRAMs or explicitly justify a
compiler-generated LUTRAM policy without changing semantics.

An initial byte-level application of the codec appeared to give large savings,
but that measurement treated serialized padding bytes as INT8 codes and is
superseded by the correction below.

The superseded byte-level result must not be used for capacity planning.

### Correction: serialized-word decoding

The preceding byte-level sparsity experiment was invalid for these artifacts:
each logical INT8 code is serialized as an eight-byte signed memory word. When
decoded at the declared memory width, the authenticated code tensors contain
less than 1% zero values (`c_fc` 0.87%, `c_proj` 0.95%, `q` 0.74%). The claimed
25--30% savings therefore do not apply and sparse weight packing is abandoned.
The codec remains a tested generic utility only; it is not used by the
compiler path or any resource estimate.
