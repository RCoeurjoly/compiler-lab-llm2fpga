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

## Primitive-clean JSON and placement runtime

Applying the fine arithmetic legalization before the final LUT/FF maps, then
the compatibility map and standard whitebox conversion, produced
`no-bscan-prim2.json` (SHA-256
`981ec1bf946963f7a9d1b58d5cf2425ef32d1a12dfb53b6c89ef6f9971dd4360`).  Its
inventory contains 52,957 LUT3, 32,273 LUT6, 18,028 FDRE, 7,583 CARRY4,
1,832 RAMB18E1, 717 RAMB36E1, and 240 RAM64X1D cells, with no generic
flip-flop or single-port RAM cells.

Nextpnr accepted this JSON and entered analytical placement after packing all
constrained I/O, BSCAN, MMCM, clocks, and memories.  It produced no error or
FASM during observation; the run was terminated after the placer remained in
the analytical phase for over ten minutes (console SHA-256
`d1edd35ddf8d0c0b35e08e476a0a2032d24ee8b5f89de032779c519fa4684414`).  This
is now a placement-runtime/resource-pressure issue rather than a netlist
compatibility crash.

## Pack-only and placement-only follow-up

The same primitive-clean JSON passed nextpnr's pack-only flow at the fixed
device, XDC, 30 MHz target, and seed 15 in 23.5 seconds. Packing consumed
1,832/1,910 RAMB18E1 (95%), 717/955 RAMB36E1 (75%), 194,378/597,200 slice
LUTs (32%), and 18,184/597,200 slice flip-flops (3%). This confirms that the
netlist is packable and has nominal device capacity; pack-only does not prove
placement, timing, routing, or bitstream generation.

A subsequent placement-only run with the same inputs and seed entered the
main analytical placer after packing, but produced no placement completion,
timing report, or FASM before it was stopped. Its console is retained at
`/tmp/llm2fpga-integrated-map/no-bscan-prim2-noroute-900.console`. The current
implementation gate therefore remains blocked on placement runtime/resource
pressure, not on simulation or netlist legality.

For comparison, the alternate `--placer sa` mode with the same device,
constraints, frequency, seed, and `--no-route` did not reach the main placer
within the bounded observation window: it was still placing the initial
222,851-cell population (1,500 cells reported) when stopped.  This rules out
that placer as an immediate runtime improvement; the default heap placer
remains the reference backend configuration.

## Quality-ABC negative control

A bounded comparison replaced `abc -fast` with the pinned quality-oriented
`abc -lut 6` script while keeping the same flattened RTL and final mapping
steps.  It did not emit a JSON handoff within the observation window and was
stopped while still producing repeated BRAM-port resize diagnostics.  The
console is retained at
`/tmp/llm2fpga-integrated-map/no-bscan-quality-yosys.console`.  This experiment
does not improve the implementation path; the existing fast-ABC JSON remains
the only placement input with a successful pack checkpoint.

## Pre-mapping optimization and FF legalization

Applying `opt -fast; opt_clean` before device mapping produced a 33.6 MB
RTLIL checkpoint (`no-bscan-preopt.il`). Mapping it with the pinned XC7
arithmetic/LUT rules and explicit DFF/DFFE/SDFFE legalization, followed by the
compatibility map, produced `no-bscan-preopt-fflegal.json` (SHA-256
`d4ab5db003bf8f258bd9c14f8d594e08779a4e210fdbd35d19d23f674c85773f`). Its
inventory has 18,028 FDRE, 11,342 INV, 7,583 CARRY4, 1,832 RAMB18E1, and
717 RAMB36E1, with no residual generic flip-flop cells. This is a valid
nextpnr handoff candidate; placement and timing remain unproven.

The legalized handoff also passes the fixed nextpnr pack-only gate in 23.7
seconds with the production XDC, 30 MHz target, and seed 15.  Packing reports
the same 1,832/1,910 RAMB18E1 (95%) and 717/955 RAMB36E1 (75%) utilization as
the earlier candidate.  This removes the residual FF compatibility failure,
but does not by itself establish placement or routing.

The legalized handoff was also probed with nextpnr's `--placer-budgets` mode
and routing disabled.  It reached the same initial analytical-placement stage
with 144,929 cells and produced no placement result in the bounded window.
Changing placer weighting therefore does not remove the current backend
scalability bottleneck.

## Persistent placement timebox

The primitive-clean legalized handoff was run through the complete pinned
nextpnr invocation with FASM output requested, seed 15, 30 MHz, and the
production XDC.  After 900 seconds it had produced no FASM or timing report;
the retained console (SHA-256
`b6f759bc5d11e86764dc59ad12977f40b4f3af21ff8ae1a056c64db5860fbd91`) ends at
`Running main analytical placer.`  This is a terminal placement-timeout
observation, not a successful route.

## Hardware-top nextpnr progression

### Flat Calyx emission: pack/place/route checkpoint

The authenticated `model.futil` was re-emitted with pinned Calyx 0.7.1 using
the non-nested Verilog backend and `--disable-verify` (the latter suppresses
backend-only `$fatal` checks that are not synthesizable by this Yosys flow).
This is an experimental compiler emission, not yet a functional replacement:
its generated SV has not completed the exact 16-token simulation gate.

The generated SV SHA-256 is
`c6426efd5750959916359670dc60fd2b04ae7282288de708937cda32624daf58`.
After integrating the production YPCB top and applying the existing pinned
Yosys XC7/LUTRAM/FF compatibility sequence, the JSON handoff SHA-256 is
`2024b689755d5a09b29a029e9c1fed0e632ae75871a33d4b99f92576d17f52e4`.
Unlike the earlier nested handoff, this candidate packs and places promptly:
nextpnr reports 70,889 `SLICE_LUTX` (11%), 6,226 `SLICE_FFX` (1%), 1,534
`CARRY4`, no BRAM/DSP, one BSCAN, and one MMCM.

Full routing completed with zero unrouted nets, but the implementation gate
failed timing.  The final routed report gives `accelerator_clk` a maximum
frequency of 11.42 MHz against the required 30 MHz; CSR scan clocks pass.
The retained console SHA-256 is
`208b043ec5eb59cd224c1fee1021a5a787ba97b2141f8d1c467829c82ea848dd`.
The emitted FASM is therefore not an accepted bitstream: the nextpnr process
exited nonzero after reporting the timing error.  The first critical path is
start/control fanout into the generated FSM guards (about 21.6 ns logic and
65.9 ns routing), providing an evidenced target for the next compiler/backend
optimization.  No board programming or hardware inference has been attempted
from this candidate.

### TDCC replication probe

The pinned Calyx compiler exposes the relevant control optimization.  Its
correct pass-qualified option syntax is
`-x 'tdcc:duplicate-cutoff=1'`; the dotted form is silently ignored.  With
that option, the emitted SV contains two replicated FSM state registers
(`fsm0_out` and `fsm1_out`) and distributes the state guards between them.
This directly targets the measured high-fanout path while remaining a Calyx
compiler transformation rather than handwritten RTL.

The candidate passed Calyx emission and the bounded pre-map Yosys elaboration.
The generic `memory_map`/ABC expansion was then stopped after roughly eight
minutes and 9 GB RSS without producing a JSON handoff.  It is therefore an
optimization hypothesis, not an accepted implementation result; the next
iteration must apply replication within the project’s staged memory mapping or
use a bounded compiler-side control partition that does not trigger this
expansion.

The staged mapping was subsequently completed with the XC5-compatible BRAM
templates (mapped JSON SHA-256
`ed4005aa25c358ac9267b026ec8d72392470720d9170e9fc651d5dace0a3f317`).
Nextpnr pack-only accepts that handoff, but full placement rejects the emitted
legacy `RAMB36` primitive (`core.attention_exp_lut_q1_20.mem.0.0`) because the
Kintex database requires `RAMB36E1`.  This is a separate primitive-ABI issue,
not evidence about the FSM replication timing; no FASM or timing result is
accepted from this branch.

A JSON-only rename of legacy `RAMB36/RAMB18` cells to `RAMB36E1/RAMB18E1` was
also attempted as a diagnostic.  Nextpnr aborted during packing with
`Assertion failure: port.net == nullptr`, showing that the interfaces and/or
parameterization are not name-compatible.  The rename was discarded and is
not a compatibility fix.

Using Yosys's `brams_xc6v_map.v` instead emits native `RAMB36E1` and
`RAMB18E1` cells.  Nextpnr pack-only then accepts the primitive ABI, but the
candidate consumes 1,029/955 `RAMB36E1` blocks (107%), so it cannot fit the
target Kintex-7.  This establishes the next tradeoff: retain the replicated
FSM only with an explicit BRAM/LUTRAM partition that stays within capacity.

A one-hot TDCC encoding probe (`-x 'tdcc:one-hot-cutoff=512'`) was also
emitted and passed the same staged mapping and pack-only gate.  It changes the
FSM state register to 407 bits but leaves the memory footprint unchanged:
nextpnr still reports 1,029/955 `RAMB36E1` (107%).  Thus control encoding alone
does not resolve the fit frontier.

### BRAM consumer inventory

The native-E1 JSON handoff was grouped by logical memory name before attempting
another placement run. It contains 1,035 BRAM primitives (1,029 `RAMB36E1` and
6 `RAMB18E1`). The dominant consumer is the token-weight code banks (852
primitives); transformer working/state memories account for 70, activation and
attention tables 36, scales 35, and biases 6. This identifies memory placement,
not FSM encoding, as the primary fit problem: at least 74 `RAMB36E1` equivalents
must be removed to get below the 955-device Kintex limit.

A bounded RTLIL experiment forced the annotated small scale/bias/LUT tables to
`ram_style=distributed`. The mapping log contained 134 block-RAM and 27
distributed-RAM mappings, versus 251 and 25 respectively in the unpartitioned
probe. This is only a partition diagnostic: it did not yet produce a complete
primitive-mapped JSON or timing result, so it is not a fit or bitstream claim.
The next implementation step is to apply the same partition through a
compiler-owned, restartable mapping stage and then rerun native-E1 packing.

The integrated partitioned handoff was flattened and native-techmapped. After
adding the standard primitive aliases, nextpnr reached constant packing, I/O
buffer insertion, clock preparation, carry/LUT packing, and distributed-RAM
packing. The current bounded probe then stops on unsupported `RAM64X1S`/
`RAM128X1S` cells emitted by the LUTRAM techmap (224 cells total); these are a
toolchain-compatibility issue, not a fit or timing result. The next repair must
map these single-port primitives to the supported Kintex dual-port LUTRAM ABI
while preserving their address/data semantics, then rerun pack-only.

### Reproducible partitioned-core checkpoint

The repository `run_bram_production_sv.py` path was updated to select the
validated immutable projection-code ROMs and token-scale banks for distributed
RAM. A fresh Nix run generated `model.sv` (SHA-256
`a7c658626a94cf21e766872bdbe589783b5f256851cbf571ceefb25563903d7a`) and
passed two independent exact two-token simulations, both selecting `11, 612`
at cycles `92,936,273` and `185,872,553`.

The integrated YPCB-top memory pass completed with no remaining `$mem_v2`
memories. Its RTLIL handoff (SHA-256
`b7a8b3b248b6d2e4dd49c1aeed7eb4db08b1709225d9aa437d318d6bd446d582`)
contains 55 generic block-RAM cells and 7,738 distributed-RAM cells. This is a
substantial capacity reduction relative to the 1,029-native-BRAM candidate,
but it is not yet a native-E1 JSON or placement result: serialization still
needs the established FDCE/Xilinx-library compatibility stage before nextpnr
can be run.

Rebuilding without `BSCAN_SIM` and loading both Xilinx primitive libraries
produced a flattened hardware RTLIL checkpoint (`no-bscan-flat.il`, SHA-256
`b91abccbafee098fdbffbf31a5443494f2d7729e3b73c13ed2a291b6bd7e9bde`).  Direct
ABC mapping, final cell mapping, whitebox conversion, and the established RAM
compatibility rewrite then emitted a clean production JSON
(`no-bscan-compat.json`, SHA-256
`c05b27b183427d23f2bc0879d8873e32b2a690824f50f904ac1bba0a137cfce5`).

Nextpnr no longer crashes and successfully packs the clock, BSCAN, MMCM, I/O,
and memory resources.  Placement stops because 2,262 generic `$_DFF*` cells
remain, leaving no placeable FF BEL (`Unable to place cell ..., no Bels
remaining of type '$_DFF_PP1_'`; console SHA-256
`23fe9bb323fb3e144d48c490f529515373319fb6db4b2652c5cafdb7403053f8`).  This
is the current implementation blocker; RAM and transport compatibility are
now past the earlier failure points.

## Direct ABC checkpoint

Running a single `abc -fast -lut 6` pass on `flatten-optfast.il` completed in
about 32 seconds and emitted `abc-direct.il` (SHA-256
`d8666841b5826476ff9dd0e17acddb6ea0b4df22a9f8fd51f29611e102f5d45d`).  This
confirms that the timeout is concentrated in the full Xilinx fine-stage
wrapper, not in ABC LUT mapping alone.  The subsequent FF/I/O cell-map
attempt still exposed the escaped `FDCE` simulation model to JSON, so no valid
nextpnr handoff was produced; primitive-library blackboxing must be corrected
before the next placement probe.

## Staged fine/cell-map timebox

Using Yosys's documented `fine:map_cells` range from the successful coarse and
memory checkpoints did not produce a handoff within 240 seconds (exit status
124; no JSON; empty redirected log SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).  The
coarse and memory stages remain fast, while fine/cell mapping is now the
measured dominant stage.  Further work should partition or simplify the
compiler-generated arithmetic before this stage, rather than increasing
timeouts indefinitely.

## Staged synthesis checkpoint

Starting from `flatten-optfast.il`, the coarse arithmetic stage
(`cmp2lut`/`cmp2lcu`, `alumacc`, `opt -fast`, and `memory -nomap`) completed in
approximately 20 seconds and emitted `coarse.il` (SHA-256
`08147dbcdbf17ef7f8935e6f7365525dda75d7290be7ee480c72f664cde50579`).  The
following combined BRAM/LUTRAM mapping also completed and emitted
`memory-mapped.il` (SHA-256
`cb3dc69939fb095473fde4147286d98480207919aee3811239657716e1845e6d`).

An initial attempt to invoke the later `synth_xilinx` stages directly failed
at JSON emission because the Xilinx `FDCE` simulation module still contained
processes.  This is a stage-invocation issue, not a semantic or timing result;
the next attempt must use the documented `fine`/`map_cells`/`map_ffs`/
`map_luts` sequence with primitive libraries handled as black boxes.

## ABC9 backend diagnostic

Replacing the default ABC pass with Yosys `synth_xilinx -abc9` did not improve
the bounded result: synthesis from `flatten-optfast.il` also reached the
300-second timeout (exit status 124), with no JSON emitted (log SHA-256
`97efecc3086ef2fa1c635368899f4074dcdf4b3e9b0e52b0e319e1430457e4e9`).  The
runtime problem therefore persists across both available combinational
optimization backends.

## Post-flatten optimization checkpoint

Running `opt -fast; opt_clean` after flattening reduced the RTLIL from
approximately 1.37 million to 493,398 cells and from 895 MiB to 348 MiB;
the resulting `flatten-optfast.il` has SHA-256
`ec5249cc749648757b243b8ad1008fe2a19b82c7b67ade7a08236fc0c18e358f`.
Nevertheless, full XC7 synthesis plus compatibility mapping still exceeded a
300-second bound (exit status 124; log SHA-256
`97efecc3086ef2fa1c635368899f4074dcdf4b3e9b0e52b0e319e1430457e4e9`).  No
nextpnr JSON was emitted.  This optimization materially reduces expansion but
does not yet make the compiler-generated design implementation-ready.

## Alternative synthesis diagnostic

Disabling DSP inference did not make the monolithic path tractable: flattened
XC7 synthesis with `-nodsp` also hit a 120-second timeout (exit status 124)
without producing JSON.  The flatten-only checkpoint is already 895 MiB and
contains approximately 1.37 million RTLIL cells, versus 429,287 cells in the
hierarchical synthesis report.  This confirms that hierarchy expansion and
subsequent generic optimization, rather than only DSP inference, dominate the
cost.  A compiler/backend partitioning or structural sharing solution is
required before a nextpnr-compatible flat handoff can be generated.

## DSP-stage timebox

To separate flattening from arithmetic mapping, the flattened RTLIL was run
through `synth_xilinx -run map_dsp:` with a 600-second timeout.  The process
reached the timeout (exit status 124) without emitting the post-DSP RTLIL;
the redirected log was empty (SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).  Thus
the current full-design DSP mapping exceeds ten minutes even before memory
mapping or JSON emission.  Any optimization must preserve the exact generated
RTL contract while reducing this pass's monolithic workload.

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

## Partitioned native-pack retry

The regenerated partitioned handoff passed nextpnr I/O, clock, carry, LUT, and
distributed-RAM packing after the single-port LUTRAM compatibility rewrite. It
then stopped on `Failed to get direction for port 'ADDRA'` for an integrated
`RAM64M` cell. This is a primitive-definition/port-metadata mismatch in the
flattened handoff, still before resource-fit or timing measurement.

Adding explicit `port_directions` maps to every generated primitive cell clears
the direction error. nextpnr then completes I/O, clock, carry, LUT,
distributed-RAM, and BRAM entry, but aborts in BRAM packing at
`design_utils.cc:93` (`port.net == nullptr`). This is now a narrower native BRAM
wiring/ABI issue; no fit or timing result follows until that assertion is
resolved.

The no-`HAS_SIZE_36` variant was then given explicit primitive directions and a
mechanical `RAM64X1S`/`RAM128X1S` to dual-port LUTRAM compatibility rewrite.
nextpnr completed packing (including BRAM packing) without an assertion, but
reported 1,810/955 `RAMB36E1` (189%), 68,354 LUTs, and no DSPs. Thus this mode is
ABI-compatible but does not fit; the original `HAS_SIZE_36` mode fits the
logical capacity frontier better but triggers the narrow-RAMB36 packer bug.

As a bounded diagnostic, the integrated memory mapping was repeated without
Yosys's `HAS_SIZE_36` flag. The resulting handoff contains 102 generic
`__XILINX_BLOCKRAM_TDP_` cells and 7,738 LUTRAM cells, versus the 55/7,738
partitioned result with `HAS_SIZE_36`. This confirms that the flag changes the
narrow-memory mode selection; native techmapping and packing of this variant
remain pending, so it is not yet a fit result.

## Project-locked nextpnr recheck

The non-`BSCAN_SIM` compatibility handoff was rerun with the exact
project-locked `RCoeurjoly/nextpnr-xilinx` stable-backports tool and matching
Kintex-7 chip database (seed 15, 30 MHz, production XDC). The fork successfully
packed the BSCAN primitive, MMCM, global clocks, distributed RAM, and BRAM, and
reported `RAMB18E1` 1,832/1,910 (95%) plus `RAMB36E1` 717/955 (75%). It then
stopped at placement because 2,262 generic flip-flop cells remained and no
`$_DFF_PP1_` BELs were available. The log SHA-256 is
`23fe9bb323fb3e144d48c490f529515373319fb6db4b2652c5cafdb7403053f8`.

This confirms the current blocker is deterministic placement/FF legalization
in the hardware handoff, not the earlier BRAM assertion and not timing yet.
No FASM, routed design, or board-test bitstream has been produced.

## FF-legalization diagnostic

Applying the standard Xilinx FF techmap to the same compatibility handoff
removed most generic sequential cells, but exposed additional generic forms
(`$_DFF*`, then synchronous-reset forms and simple Boolean cells) during
nextpnr's transforms. A narrowly scoped diagnostic map could advance the
failure from generic FF placement to generic gate placement, but its JSON
expanded to roughly 1 GB and did not produce a stable P&R handoff. It is not an
accepted RTL/compiler fix. The next implementation step is to integrate the
complete technology-mapping sequence at the pipeline boundary, then re-run the
same deterministic P&R gate; no handwritten accelerator logic is implicated.

## Placer-mode comparison

The existing pre-optimized/FF-legalized handoff was also run with the locked
nextpnr fork's simulated-annealing placer, `--no-route`, `--no-tmdriv`, and
`--timing-allow-fail` (seed 15, 30 MHz). After 120 seconds it was terminated
while still performing initial placement, at 9,500 of 222,851 cells; no placed
JSON or timing result was emitted. The console/log SHA-256 is
`6739aa391490e2f6fd739fa243bcaea23df324ceeaa632aaa08546e5f2f3a0e8`.

This bounded comparison does not show a viable alternate placer. The current
backend issue is netlist-placement scale, and the next fix must reduce or
structure that scale in the compiler-owned mapping sequence without changing
the model contract.

## Checkpointed standard XC7 mapping

The repository's standard `synth_xilinx` sequence was then executed as
restartable checkpoints: `begin:prepare` (RTLIL SHA-256
`daca78b9a95ed5afc39f0f6503c94fe438e2728505d2ac6cf9c1842e35f8d3d0`),
sequential legalization (`c2d5bca16f3dc004add2ae4196e3f097f32c2c44fe0382a6f374303887ac9ed7`),
arithmetic mapping (`de0fe967d902f7ee04761da82468864b27960212d4e7a4d0b5c00e900111d8c7`),
and memory mapping (`a47684d2142d281bc14a40604651c0ac27d627598c93a8d8dbf5217992cf0c56`).
The mapping stage completed in about 151 CPU seconds and passed Yosys checks.

After the established RAM64X1S compatibility transform and explicit
RAM64X1D directions, the locked nextpnr pack-only gate passed. Its handoff
contains 59,446 LUTs, 16,773 FFs, 4,866 CARRY4s, 253 DSPs, 1,832 RAMB18E1s,
and 717 RAMB36E1s. The pack log SHA-256 is
`d0d43640f88d702ea15b037a5ed679d36177f7534b0b609cb8623a9041c618a2`.

A 300-second placement-only run reached the initial analytical placer with
31,546 cells but produced no placement result. This is a substantial reduction
from the earlier 144k/222k-cell handoffs, and establishes a reproducible,
packable compiler backend checkpoint; placement scalability remains the next
blocker.

The pack-only gate was repeated with the same handoff, tool, XDC, seed, and
30 MHz target. It passed with the identical checksum (`0x03a8ffc8`), resource
counts, and log SHA-256 `d0d43640f88d702ea15b037a5ed679d36177f7534b0b609cb8623a9041c618a2`.
This establishes deterministic mapping/packing; placement remains the only
backend gate not reached.

## Selective-memory mapping checkpoint

Using the current generated `model.sv`, memory modules were mapped before
flattening with the existing BRAM/LUTRAM libraries. This completed in about 10
CPU seconds and produced a 31 MB RTLIL checkpoint (SHA-256
`4fffb35f16b741bef236e2b4e50b2f355142e47a7f6de1480096fb3bb617ce1c`). A
bounded `opt -fast` arithmetic pass then completed in about 73 CPU seconds,
but its output still contained generic memory wrappers and was not a P&R
handoff. Adding the final `map_memory` stage re-entered the known global
optimization loop and emitted no checkpoint within the bound. This isolates
the remaining cost to final primitive legalization after selective mapping.

Running the RAM techmap primitives explicitly (`lutrams_xc5v_map.v` followed by
`brams_xc6v_map.v`) on the fast checkpoint completes in about 9 CPU seconds and
emits a complete 215 MB RTLIL file (log SHA-256 `a300ea4479`). JSON emission
still requires the pipeline's primitive-library blackboxing and port-direction
stage: direct serialization fails on process-bearing `RAM32M` definitions.
Thus explicit RAM techmapping is not the remaining time sink; producing a
nextpnr-compatible JSON without losing the full flattened design is the next
integration task.

## Final legalization and nextpnr handoff probe

The final arithmetic/FF/LUT mapping stage completed within the bounded run and
emitted a 183 MB RTLIL checkpoint (`/tmp/partitioned-final-mapped.il`).  The
initial JSON emission failed because the simulation definitions for `RAM32M`
and `RAM64M` still contained processes.  Removing only those two
process-bearing library definitions (while retaining the other primitive
metadata) allowed Yosys to emit a 243 MB JSON handoff
(`/tmp/partitioned-final-narrow.json`).

The first deterministic nextpnr pack attempt then exposed a separate ABI issue:
the handoff contains LUT cells for which this nextpnr build cannot infer the
`I0` port direction (`$abc...` cell).  A temporary function-preserving
LUT2--LUT5-to-LUT6 INIT expansion did not change that diagnostic.  Therefore
the design has reached JSON emission, but has **not** reached a valid nextpnr
pack/placement handoff or timing closure.  No FASM or board bitstream follows
from this probe.

Injecting primitive port directions from the mapped library definitions lets
nextpnr pass LUT, clock, DSP, and I/O packing. It then rejects the 160
`RAM64X1S` cells as an unsupported primitive. A temporary conversion to
dual-port `RAM64X1D` (duplicating the read address and preserving `INIT`) gets
past that unsupported-cell check but triggers the nextpnr assertion
`port.net == nullptr` during DRAM packing. This is now the narrowest observed
implementation blocker; it is still a temporary handoff experiment, not a
committed RTL change or a fit/timing result.

Mapping the isolated 4×16 `csr.prompt_words` memory with Yosys `memory_map`
removes the last `$mem_v2` cell without touching the model memories. With the
same temporary read-only-RAM-to-LUT legalization and primitive direction
metadata, nextpnr enters placement: it packs 56,525 LUTs, 1,680 RAMB18E1s,
520 RAMB36E1s, 330 DSP48E1s, and the constrained clock/I/O resources. The
bounded 300-second placement run reaches the main analytical placer for
114,105 cells but emits no placement or timing result before the timeout.
Thus the immediate blocker has moved from JSON/packing correctness to
placement scalability; there is still no timing-closed implementation or
bitstream.
