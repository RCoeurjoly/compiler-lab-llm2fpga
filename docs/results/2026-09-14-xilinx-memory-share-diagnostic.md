# TinyStories-1M generated-SV memory-sharing diagnostic

This diagnostic separates functional correctness from Xilinx technology
mapping for the narrowed compiler-generated TinyStories-1M artifact.

## Inputs

- Generated SystemVerilog: `/tmp/llm2fpga-narrowed-full16-sim/model.sv`
- SV SHA-256: `b6426ac851e42885e3fbda0d40493a06d568949ff6b3cbcdd25c1d5ff992bfbc`
- Functional receipt: `/tmp/llm2fpga-narrowed-full16-sim/production-execution.json`
- Functional result: two independent 16-token simulations passed exactly.

## Results

The normal `synth_xilinx -family xc7` flow did not produce a report; it stalled
in Yosys `MEMORY_SHARE` during the `memory -nomap` stage.  The corresponding
bounded diagnostic completed in 8.26 seconds with memory SAT sharing and port
widening disabled:

```text
nix develop -c yosys -p \
  'read_verilog -sv /tmp/llm2fpga-narrowed-full16-sim/model.sv; \
   hierarchy -top main -check; proc; flatten; opt; memory_dff; \
   memory -nomap -nosat -nowiden; opt_clean; stat'
```

The resulting structural netlist contained 19 collected `$mem_v2` memories,
14,014 cells, and 39 multipliers.  The diagnostic log is
`/tmp/llm2fpga-narrowed-full16-memory-nosat.log` (SHA-256
`aa7673cd3e35d78c84340991e45728f819433cb96a0288107d13acaede85d6ee`).

This proves that the generated memories can be elaborated and collected when
the unbounded sharing heuristic is disabled.  It does **not** prove BRAM
mapping, device fit, timing closure, bitstream generation, or hardware
execution.  The next backend experiment is to map these collected memories to
the XC7 BRAM library with the same `-nosat -nowiden` policy and measure the
actual RAMB36E1 count before attempting nextpnr.

An initial direct mapping attempt did not reach mapping: the repository's
`/tmp/yosys-data2/xilinx/brams_xc7.txt` uses an older `ram block` rule syntax,
which Yosys 0.66 rejects before reading the design. A compatible rule file is
now checked in at `fpga/synthesis/xilinx-xc7-bram-rules.txt`. With that file,
`memory_bram` completed and converted all 19 memories to generic
`$__XILINX_BLOCKRAM_SDP_` cells. The subsequent primitive techmap still needs
to be integrated with the repository's XC7 wrapper; it did not replace those
generic cells in this standalone probe.

The generic cells use Yosys-generated `A1*`/`B1*` ports, whereas the historical
XC7 map wrapper expects `PORT_A_*`/`PORT_B_*`; this explains why the unmodified
techmap was a no-op. A temporary adapter wrapper made replacement execute and
produced 19 `RAMB36E2` instances, but that count is not accepted as a resource
result: the deliberately broad rule uses one abstract 72-bit, 15-address-bit
variant and does not account for the physical depth/width banking required by
each memory. Width/depth-specific variants and an integrated adapter are still
required.

## Model-image initialization correction

The generated SV's normal Verilator path preloads every source memory from
host-side binary files. The earlier static-image helper incorrectly inserted
hierarchical `$readmemh(..., instance.mem)` calls into `main`; Yosys rejected
these because the second argument is not a local memory. Commit `bf2821a`
provided a BRAM rule file, and the follow-up staticizer change moves each image
initializer into the memory implementation behind an `INIT_FILE` instance
parameter. A regenerated static image contains 89 authenticated image files,
three local `readmemh(INIT_FILE, mem)` initializers, and parses successfully
through Yosys hierarchy checking. This establishes synthesis-visible model
initialization, but does not yet establish BRAM banking, timing, bitstream, or
board execution.

With the static image present, Yosys retained 107 memories totaling
32,947,488 logical bits (31.42 MiB-equivalent bits) after collection. The
width/depth-specific banking rules expanded these to 1,034 generic SDP BRAM
wrappers before primitive techmap. This is already 79 blocks over the YPCB
955-RAMB36 budget, even before accounting for non-memory logic and packing.
The earlier 1,034 figure is therefore the first meaningful pre-placement fit
signal; reducing only the runtime scratch memories cannot close the gap.

A width/depth-variant probe (using 1/2/4/9/18/36/72-bit configurations) also
completed. It created 63 generic SDP wrappers with configurations
`(abits,dbits) = (9,72)×35, (10,36)×24, (11,18)×2, (13,4)×2`. A temporary
port adapter techmapped these to 63 `RAMB36E2` cells. However, those wrappers
represent only 2,314,240 bits of nominal primitive capacity while the source
design reports 34.8 Mbit of logical memories. This discrepancy shows that
initialized/constant memory accounting and/or banking duplication is still
wrong; the 63-cell result must not be treated as a fit estimate.

## Memory-placement probe (2026-09-15)

A temporary generated-SV probe changed 17 transient activation/attention
instances from `seq_mem_d1_bram` to `seq_mem_d1_lutram` and reran the same
`memory_bram` rule flow. The result remained 1,022
`$__XILINX_BLOCKRAM_SDP_` cells. Therefore the current `memory_bram` stage
does not honor this module-level variant as a placement decision after
flattening; merely renaming the generated memory primitive cannot recover the
67-block deficit. A real distributed-RAM pass must act before flattening or
emit an explicit LUTRAM implementation, then be rechecked for LUT/FF cost and
functional equivalence.
