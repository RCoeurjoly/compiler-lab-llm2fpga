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

### Current full-16 logical lower bound (2026-09-14)

Regenerating the current compiler plan for all 16 continuation steps reports
108 planned memories and 1,104 legal-bank equivalents.  Its logical storage
is 35,418,112 bits, an ideal lower bound of 984 RAMB36E1 blocks.  Immutable
authenticated sources account for 32,407,552 bits (901 ideal blocks), leaving
only 54 ideal blocks under the 955-block device budget for all runtime state.
Consequently, physical packing alone cannot make the current 20-row schedule
fit: the compiler must reduce the simultaneously resident context/workspace
state (for example with real context tiling and streaming) before a BRAM-only
full-16 design can be feasible.

The accumulated compiler source was regenerated for `generation_steps=16` and
lowered by the pinned Calyx backend without executing the long simulation. The
Futil hash is `a633a364482ea387302edaa66349c44bede505b9ef13f73ec8ab8a881db70b01`
and the generated SV hash is
`93c38f296106735f16f96984925edc3de47e4f46d55070a066b8210e9021769a`.
Calyx emitted its known data-path-inference convergence warnings but returned
successfully. This is a reproducibility/elaboration receipt, not semantic,
timing, fit, or hardware evidence.

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

### c_fc accumulator/output reuse candidate (2026-09-14)

The compiler's explicit lifetime-reuse map was extended to coalesce
`c_fc_accumulator_i64` with `c_fc_output_q16_16`.  The generated Futil and SV
passed the exact two-token harness twice, with both runs selecting `11, 612`
at cycles `92,936,273` and `185,872,553` and completing at cycle
`185,872,559`.  The production receipt records oracle hash
`7c306e8b6e38e94f54a13b8434c6dff720d0cccfb7a9e9c749198f3dde93f74`, Futil
hash `10da5ffffb0e780475aa6a7a402934f3669bd0aea6ecbc10094e836915ad12ab`,
and SV hash `e43159fb56eb48b2491fb5df2b84987a0ca19627dfa6852084fd4b2b277bb92c`.
Xilinx-family Yosys synthesis completed in 37.9 seconds and inferred 1,013
`RAMB36E1` and 322 `DSP48E1` cells, a four-BRAM reduction from the preceding
1,017-cell candidate.  This remains a two-token simulation/resource
checkpoint; it is not a full-16-token or board-fit result.

### c_fc post-rescale/output reuse candidate (2026-09-14)

The next compiler lifetime-reuse candidate coalesces
`c_fc_post_weight_rescale_bias_q16_16` with `c_fc_output_q16_16`.  Generated
SV again passed two independent exact two-token runs (`11, 612` at cycles
`92,936,273` and `185,872,553`, completing at `185,872,559`).  The receipt
records Futil hash
`e9acb685eb162f8fb1a4a2c54f5bcf07faf712b5f882d61ef093e7fdd44c4158` and SV
hash `c73146bb3aee17a247d5bdc32548a6595395c60bc4b913a3d2fb89859e290d20`.
Xilinx-family synthesis completed successfully in 37.9 seconds with 1,009
`RAMB36E1` and 322 `DSP48E1` cells.  This is another four-BRAM reduction;
the candidate remains a two-token simulation/resource checkpoint and does
not establish full-16-token correctness, fit, timing, or board execution.

### c_fc/GELU in-place reuse candidate (2026-09-14)

The compiler then coalesced the elementwise `gelu_output_q16_16` buffer with
`c_fc_output_q16_16`; each input word is read before its address is overwritten.
The generated SV passed two independent exact two-token runs (`11, 612` at
the authenticated checkpoint cycles).  The receipt records Futil hash
`9be3f23e5374e0bd146f99ff478b8b834b5b63e3af34c54a2a69102855a1eafa` and SV
hash `2019565fe2762cfa1ac679ba74cf32f772b9107603621e6cc45942120d7127de`.
Xilinx-family synthesis completed successfully in 37.9 seconds with 1,005
`RAMB36E1` and 322 `DSP48E1` cells, a further four-BRAM reduction.  This is
still a two-token simulation/resource checkpoint; full-16-token semantics,
fit, timing, and board execution remain outstanding.

### Attention numerator/context reuse candidate (2026-09-14)

The compiler coalesced the serial `attention_numerator_q17_36` and
`attention_context_q16_16` buffers. Both independent exact two-token
generated-SV runs passed (`11, 612` at the authenticated checkpoint cycles).
The receipt records Futil hash
`b618041db2e9da7bd498962dd465dbd7e1994738f0d747c2ff8ea3684b66ac8d` and SV
hash `57d122d706492057af5595537f4d666c0409af4a9d44bd08a862760ef06c30f3`.
Xilinx-family synthesis completed successfully with 1,004 `RAMB36E1` and 322
`DSP48E1` cells. This saves one further BRAM; full-16-token semantics,
timing, fit, and board execution remain outstanding.

### Attention context/residual reuse candidate (2026-09-14)

The compiler coalesced `attention_residual_q16_16` with
`attention_context_q16_16`. Both independent exact two-token generated-SV
runs passed (`11, 612` at the authenticated checkpoint cycles). The receipt
records Futil hash
`2f2d12b57ed36a20e3ac6400743422556715c9597a282e25df9c551cff1fd442` and SV
hash `359ec0beffb596d7be20ff30296025a4c68b2ab9721b46a0be015e626ae7bb70`.
Xilinx-family synthesis completed successfully with 1,003 `RAMB36E1` and 322
`DSP48E1` cells. This saves one further BRAM; full-16-token semantics,
timing, fit, and board execution remain outstanding.

### Projection post-rescale buffer reuse candidate (2026-09-14)

The compiler coalesced the serial q/k/v/out post-weight-rescale buffers with
`attention_context_q16_16`. Both independent exact two-token generated-SV
runs passed (`11, 612` at the authenticated checkpoint cycles). The receipt
records Futil hash
`949a011aada281a7659e851d3b5c403fc813e8829e9ff09318d56b605187b5e7` and SV
hash `a3fd0f34d1c98caefba22e87ba295823865b07bc68ba20f4148d2ba55ae2d8b8`.
Xilinx-family synthesis completed successfully with 999 `RAMB36E1` and 322
`DSP48E1` cells, a four-BRAM reduction. Full-16-token semantics, timing,
fit, and board execution remain outstanding.

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

The lexical candidate alias `final_output_q16_16 -> block_input_q16_16` was
then regenerated by the compiler and validated with the exact two-token
harness. Both runs selected `11, 612` at cycles `92,936,273` and
`185,872,553`, respectively. Its provenance records Futil hash
`5c00b1820968e8393f9cd5e3f0b2be3ec248383494eb0093a97fcb7d43605566` and SV
hash `7ceb3b597d6e5a7214d6fdc2ad17ea53011995ee3497a25eefad92f5f2adbc74`.
Xilinx Yosys synthesis inferred 1,019 RAMB36E1 and 322 DSP48E1 cells. This is
an evidence-backed alias, but it still exceeds the device budget by 64 BRAMs.

A second planner candidate, `c_proj_output_q16_16 -> ln1_output_q16_16`, also
passed the exact two-token harness twice with `11, 612` at the authenticated
checkpoint cycles. Its Futil hash is
`96af17989c89de807afc99e58f59dc883856138090bfe85186023dc999c1617e`; the
compiler plan is 1,049 banks and Xilinx synthesis inferred 1,018 RAMB36E1 and
322 DSP48E1 cells. This independently validates another one-block reduction,
but the full design remains 63 BRAMs over the budget.

A third candidate, `attention_context_heads_q16_16 -> ln1_output_q16_16`,
passed the exact two-token harness twice (`11, 612` at the same checkpoint
cycles). Its Futil hash is
`b259106c42203d2a899525cc4439dcb4633844a64d351e5887f9df1e7b0cb645`;
Xilinx synthesis inferred 1,017 RAMB36E1 and 322 DSP48E1 cells. This proven
alias leaves a 62-block gap to the YPCB budget.

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
