# Distributed-memory TinyStories-1M simulation and mapping gate

## Functional simulation

The generated artifact in `/tmp/llm2fpga-lutram-full16` was exercised with
`run_bram_production_sv.py --generation-steps 16`.  The harness performs two
independent reset/start runs, feeds back the generated token through the
token-index port, and checks every selected token against the frozen oracle.

Receipt: `production-execution.json` (SHA-256
`b6be336fde9c607157564f40d73a0c134531478e06b75024c23d90f454b7b533`).

- Status: `passed`.
- Futil SHA-256: `0d461a1e82b22956a73632d1c49f90704ff2a9838401d419ff1b8fc04a87dfc2`.
- Generated-SV SHA-256: `3af48b2cb480bbeff3fee1e582b1fc836f8e5cb50b08f235cf3dba7c67758c0e`.
- Oracle SHA-256: `7c306e8b6e38e94f54a13b8434c6dff720d0cccfb7a9e9c749198f3dde93f74`.
- Both runs selected the exact sequence
  `11,612,373,257,1310,2576,3706,20037,13,1375,6151,284,711,2354,287,262`.
- Both runs completed at `1,972,293,279` simulation cycles.

This is generated-RTL simulation evidence only.  It is not a bitstream,
timing-closure, or board-inference result.

## Technology-mapping probe

The bounded pre-flatten Yosys flow completed with the XC7 rules:

```text
read_verilog -sv model.sv; hierarchy -top main -check; proc; opt;
memory_dff; memory -nomap -nosat -nowiden; memory_bram -rules
fpga/synthesis/xilinx-xc7-bram-rules.txt; stat
```

Log SHA-256: `69c02113bef46a97650a73e1c9c7f23f63149cf0171d5c2928cd6676fc576969`.
The pass created 90 generic `__XILINX_BLOCKRAM_SDP_` cells but left 26
`$mem_v2` memories unmapped.  The post-flatten probe left all 19 memories
unmapped (log SHA-256
`fdec3e5589c6b76ac1d8c67a0d8785a4008c83af9790042985ed2db34203d1de`).
This establishes the next backend blocker: width/depth-specific rules and an
explicit distributed-RAM implementation are still needed before resource fit,
timing, or bitstream generation can be assessed.

## Generated-core ABI boundary

The generated SV was parsed independently and recorded in
`/tmp/llm2fpga-lutram-full16/generated-interface.json` (bound to the SV hash
above).  Its `main` module exposes only `start`, `valid`, `token_index`, four
16-bit prompt words, `done`, `token_id`, `clk`, and `reset`.  It does not expose
the streaming `valid/ready` channels expected by the older self-test wrapper,
nor a YPCB transport port.  The checked-in production top does connect this
ABI to the JTAG CSR (`rtl/tinystories_1m_ypcb_bram_production_top.sv`); a fresh
Yosys elaboration of that top plus this generated SV completed successfully
(log `/tmp/llm2fpga-lutram-full16/top-elaboration.log`, 12,840 cells, two
submodules).  The separate `tinystories_1m_ypcb_bram_top.sv` remains a
blackbox contract shell.  Elaboration still does not establish technology
mapping, timing closure, bitstream validity, or hardware inference.

The integrated production-top memory-inference pass also completed (log
`/tmp/llm2fpga-lutram-full16/top-memory-inference.log`, SHA-256
`cf46e3315d300be1d01956b3ea8b6f1e19a78fcd7f0e4722b32a9a5a4fa84b6b`).  It
inferred 90 generic XC7 BRAM cells but left 27 `$mem_v2` memories unmapped,
one more than the standalone core due to CSR integration.  This remains an
inference diagnostic, not a fit or timing result.

As a negative control, running `memory_bram` before versus after
`memory_dff` produced the same standalone result: 90
`__XILINX_BLOCKRAM_SDP_` cells and 26 unmapped `$mem_v2` memories.  The logs
are `memory-nodff.log` (SHA-256
`63b1c11034f2bca9cb4e8b52d59b7d0d5ee82c92e92fba4b0a1a1c52e954e1dc`) and
`memory-postdff.log` (SHA-256
`db37e1cdc6c5ce35f735bca867ad6a16f4491cec67f3e4f8e1d84a3a4cbec5c6`).
Pass ordering is therefore ruled out as the cause of failed read-port
mapping.

## Combined BRAM/LUTRAM mapping breakthrough

Yosys 0.66 `memory_libmap` succeeds when the pinned BRAM and LUTRAM libraries
are supplied together:

```text
memory_libmap -lib +/xilinx/brams_xc4v.txt -D HAS_SIZE_36 -D HAS_CASCADE
  -D HAS_MIXWIDTH_SDP -lib +/xilinx/lutrams_xc5v.txt
```

The resulting standalone design has no remaining `$mem_v2` cells.  Its final
statistics contain 957 block-RAM cells (22 SDP and 935 TDP), 10,308 LUTRAM
cells (10,260 SDP and 48 SP), and no unmapped memories.  The diagnostic log is
`/tmp/llm2fpga-lutram-full16/combined-libmap.log` (SHA-256
`250be62e5d2ae87a299ef3691ecef0e3e382cc16a59a7811e56a34815df66aa6`).  This
is a mapping result only; synthesis, placement, timing, and bitstream
generation remain to be run.

The primitive-mapped RTLIL was then checked with Yosys's Xilinx simulation
cell declarations (`+/xilinx/cells_sim.v`); hierarchy validation passed.  The
top-level aggregate contains 967 `RAMB36E1`, 22 `RAMB18E1`, 4 `RAM32M`, and
3,600 `RAM64M` instances.  This validates the primitive names and gives a
resource-count checkpoint, but arithmetic cell mapping, placement, timing,
and bitstream generation remain outstanding.

The subsequent XC7 cell-mapping stage completed and emitted
`/tmp/llm2fpga-lutram-full16/cells-mapped.il` (SHA-256
`e153215c07d319d9f9a21503f771cc724ba770237470c759f071ddcbf154f4`).  A fresh
Yosys readback and hierarchy check passed without additional libraries; the
techmap output carries its required XC7 primitive declarations.  The stage
reported only port-width resize warnings while adapting generic BRAM
templates.  This remains pre-placement and pre-timing, and the integrated
production-top wrapper has not yet been passed through this exact sequence.

The integrated RTLIL was then techmapped with the pinned XC7 BRAM and LUTRAM
templates, producing `integrated-techmapped.il` (SHA-256
`e1c468de9cfb431679c3a838fe0cbe3ffed1726bc20c3052dfd7ff24578052ad`).  The
Xilinx cell-mapping pass completed when `cells_sim.v` was loaded as a library,
and emitted `integrated-cells-mapped.il` (SHA-256
`b02463e3ffef32c518038ca9798b8f3dc0eaa0fa5bf8adf238760228e92d409f`).  The
pass reports only expected BRAM/LUTRAM port-width resize warnings.  This is
still pre-synthesis, pre-placement, and pre-timing; the remaining CSR
`prompt_words` memory and all implementation/resource limits must be checked
before a bitstream attempt.

## Integrated production-top mapping retry

After the host interruption, the integrated pass was rerun from the durable
checked-in generated RTL (`result-compiler-top-30mhz-20260908/model.sv`,
SHA-256 `cf3c83638502769966e5c26efaff7c4ec08ee1f73ad03764b45b3980b862b3ad`).
The production top, JTAG CSR, and generated core were processed together with
the same combined BRAM/LUTRAM `memory_libmap` recipe. Yosys completed with exit
status 0 and emitted `integrated-mapped.il` (SHA-256
`9a107e9a0d319cc6f9802761b0a6559481ed3771d129db0a87229673661761eb`).

One `$mem_v2` remains for the CSR `prompt_words` storage; the generated-core
memories are mapped. This is a successful integrated mapping checkpoint, not
yet synthesis, placement, timing closure, bitstream generation, or hardware
inference.

## Flattening diagnostic

Flattening the integrated RTLIL by itself completed and produced
`flatten-only.il` (SHA-256 `4719d375ca7069cf6d89b52eee877e8fff9bad5a1e758c5e9ca1e886c2540ef4`).
However, flattened XC7 synthesis plus compatibility mapping did not finish
within the 180-second bounded limit (exit status 124; log SHA-256
`db60495d0929cdbdd0df88c4ebe10c3e1609c6a50fc2fd9ab3cd3b8532dbc5a8`).  This
separates the earlier nextpnr crash from a second scalability problem: the
flattened backend path is currently too expensive to produce a handoff JSON.

## Deterministic nextpnr probe

The synthesized JSON (`integrated-synth.json`, SHA-256
`2f2f63bdb60b449c124d08873a8372e87831d41efe0edba1b522d7e35cd65d20`) was
submitted to the pinned `nextpnr-xilinx` for `xc7k480tffg1156-1`, the
production XDC, seed 15, and a 30 MHz target.  The process aborted before
packing with `std::out_of_range` (`__n (which is 12595) >= this->size() (which
is 0)`); console SHA-256 is
`533ee3d1b74e8ceeeb931b15576068c648458477c6e4f6ba1256d551954339be`.  No
FASM or routed output was produced.  This is a reproducible nextpnr input/
primitive compatibility crash, not a timing failure; the next investigation
must compare the emitted primitive JSON with the known-good route and apply
only the established primitive-compatibility mapping before retrying.

## XC7 synthesis resource checkpoint

With the CSR memory expanded to logic by `memory_map`, XC7-family synthesis
completed in 38.74 seconds (log SHA-256
`8720d54fa70ee3e128595bf178eeebadce254b51392112a9ee3a29c049fa64aa`).  The
result contains 1,055 `RAMB36E1`, 14 `RAMB18E1`, 256 `RAM64X1S`, 12 `RAM32M`,
and 429,287 total cells (including 310,395 LUT1--LUT6 cells).  Yosys emitted
4,214 unique warnings, so this is resource/elaboration evidence only; no
device-specific placement, timing, or fit claim follows from it.
