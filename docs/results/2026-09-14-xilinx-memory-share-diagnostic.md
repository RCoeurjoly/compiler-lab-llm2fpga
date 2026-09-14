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
