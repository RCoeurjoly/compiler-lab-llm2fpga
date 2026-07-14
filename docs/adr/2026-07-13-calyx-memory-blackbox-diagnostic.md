# ADR: Diagnose Calyx synthesis with external memories blackboxed

- Status: completed; diagnostic mechanism rejected
- Date: 2026-07-13

## Context

The Task 3 full TinyStories FP32 Handshake route blackboxed large memories and
still reported approximately 140x FPGA overuse. A later W8A8 result was roughly
four times smaller. The current full TinyStories PT2E W8A8 route uses TOSA,
omits Handshake, and lowers through Calyx to 74,132,122 bytes of SystemVerilog.
`yosys-slang` accepts that SV, but Yosys process expansion was killed after
reaching approximately 25.4 GiB resident memory.

The pre-`proc` design contains 10,199 Yosys structural memories and 236,744,916
memory bits. Inspection of the exported Futil provides a more precise boundary:
the Calyx wrapper contains 2,133 cells marked `@external(1)`, all instances of
`seq_mem_d1`, accounting for 236,728,784 bits.

Calyx emits one SV stream but does preserve two components as modules:

```text
main
└── main_1
```

`main` owns the concrete external memory cells. `main_1` is the compute/control
component and accesses those cells through explicit address, enable, write-data,
read-data, and completion ports. Default `yosys-slang` import flattened this
hierarchy, which is why the prior structural report contained no submodules.

## Decision

Before changing MLIR, Calyx, or introducing a DDR3 controller, run a controlled
diagnostic ablation at the SystemVerilog frontend boundary:

1. Keep `main` as the top module.
2. Parse every SystemVerilog source with `yosys-slang`.
3. Pass `--blackboxed-module seq_mem_d1`, the only memory primitive type used by
   the 2,133 Calyx-external cells.
4. Run Yosys `proc`, retain and assert the `done` output, emit structural
   statistics, and checkpoint RTLIL.
5. If process expansion succeeds, continue through the existing staged Xilinx
   7-series synthesis flow to obtain provisional LUT/FF/DSP counts.
6. Synthesize `main_1` directly only as a cross-check, not as the primary result.

This experiment intentionally changes only memory implementation visibility
relative to the prior failed `proc` attempt. It does not also enable the
experimental `yosys-slang --keep-hierarchy` option.

## Evidence policy

Blackboxing is a diagnostic ablation. It may establish whether concrete memory
elaboration caused the OOM and may measure the retained shell/control/datapath.
It is not by itself a valid DDR3 resource-saving result.

A later external-memory optimization claim requires an explicit realizable
memory-service interface, reported retained BRAM, external storage bytes,
logical-to-physical port scheduling, bandwidth assumptions, and target-specific
LUT/FF/DSP results. A board DDR3 controller may remain outside the accelerator
synthesis boundary, but its exclusion must be explicit.

## Consequences

The immediate experiment can reuse the already generated SV and directly mirror
the Task 3 blackboxed-memory question. No broad compiler redesign is required to
test the OOM hypothesis. If `proc` still OOMs, memory storage is not the sole
scaling problem and the next investigation must isolate compute/control
elaboration, including a direct `main_1` run and hierarchy-preserving options.

If `proc` succeeds, the project gains an RTLIL checkpoint suitable for staged
target synthesis. Any resulting FPGA counts remain provisional until the memory
blackboxes are replaced by a defined external-memory architecture.

## Experiment result

The run completed with exit status 0 in 55 minutes 32.72 seconds. It passed
`yosys-slang`, `hierarchy`, `proc`, `opt_clean`, and the post-`proc` `done`
assertion, then emitted a 2.1 GiB RTLIL checkpoint. Peak resident memory was
29,652,796 KiB.

The post-`proc` structural report contained:

| Metric | Count |
|---|---:|
| Processes | 0 |
| Cells | 3,116,666 |
| `seq_mem_d1` blackbox instances | 2,133 |
| Remaining memory bits | 11,746 |
| Multipliers | 1,147 |
| Flip-flops (`$dff` + `$aldff`) | 48,676 |
| Multiplexers | 829,082 |

However, this frontend blackbox mechanism is rejected as synthesis evidence.
`seq_mem_d1` is parameterized by data width, depth, and address width. The
`yosys-slang --blackboxed-module seq_mem_d1` option imported one generic module
signature rather than preserving each instance's specialization. Yosys emitted
6,057 port-resizing warnings, including data widths changed from 1, 32, or 64
bits to 8 bits and address widths changed to 16 bits. The resulting connectivity
is therefore not the original design's connectivity.

The successful run proves that a storage-free elaboration can cross `proc` on
this machine. It does not prove that concrete memory implementation was the sole
cause of the earlier OOM: this run actually reached a higher peak RSS than the
failed run, and the malformed blackbox signatures changed the design.

Do not continue this RTLIL checkpoint into Xilinx synthesis or report its cells
as an optimization result. The next diagnostic must preserve each external
memory port's exact width. The existing `main_1` component already exposes those
specialized ports and contains no wrapper memory instances, making direct
`main_1` synthesis the narrowest available cross-check.

## Corrected cross-check

- Status: accepted diagnostic result
- Started: 2026-07-14

With user approval, rerun the same frontend and process-expansion boundary with
`main_1` as the selected top, no blackboxed modules, and no experimental
hierarchy-preservation option. Require exactly one `main_1` module and one
`main_1/done` wire before and after `proc`; then emit a structural JSON report
and RTLIL checkpoint.

Acceptance requires zero memory-port resizing warnings. A successful result is
a compute/control-kernel diagnostic with exact logical memory interfaces. It is
not a full-system or DDR3 utilization result because the storage implementation,
memory-port scheduler, and physical memory service are outside this top.

The corrected run completed with exit status 0 in 53 minutes 22.99 seconds and
reported zero errors and zero warnings. Peak resident memory was 29,011,512 KiB.
It passed both `done` assertions and emitted a 1.9 GiB RTLIL checkpoint.

| Metric | Count |
|---|---:|
| Exact top-level ports | 12,802 |
| Top-level port bits | 115,933 |
| Processes after `proc` | 0 |
| Cells | 3,106,002 |
| Remaining internal memory bits | 11,746 |
| Multipliers | 1,147 |
| Flip-flops (`$dff` + `$aldff`) | 48,676 |
| Multiplexers | 820,551 |

This result validates the generated `main_1` compute/control kernel as a
width-correct, storage-externalized synthesis boundary. It also exposes the next
architectural problem: 2,133 logical memories become 12,798 memory-related top
ports in addition to clock, reset, go, and done. A DDR3 controller cannot
directly implement that interface; logical accesses must be scheduled and
aggregated onto a bounded memory service.

The exact kernel remains enormous before target mapping: 3.1 million generic
cells, including more than 820 thousand multiplexers. Externalizing storage is
therefore necessary for this experiment but is unlikely to make the current
architecture fit by itself.

## Staged Xilinx-7 mapping

- Status: blocked at SAT-based resource sharing
- Approved and started: 2026-07-14

Feed the accepted 1.9 GiB `main_1` post-`proc` RTLIL checkpoint into the same
staged `synth_xilinx -family xc7 -noiopad` sequence used by Task 3. Do not rerun
SystemVerilog import or `proc`. Each stage must assert the `done` signal, record
its runtime and peak memory, and emit an RTLIL checkpoint before the next stage.

The first stage runs only `begin:prepare`. Later coarse memory, fine arithmetic,
cell, flip-flop, and LUT mapping stages proceed only from successful checkpoints.
The objective is provisional LUT/FF/DSP and retained BRAM counts for the exact
external-memory kernel; it remains separate from a complete DDR3 system claim.

Stage 1 (`begin:prepare`) completed in 1 minute 10.25 seconds with peak resident
memory of 8,365,864 KiB. It preserved `done` and emitted a 1.9 GiB checkpoint.

The original Stage 2 (`coarse:map_memory`) was killed by signal 9 after 11
minutes 18.64 seconds at 30,201,752 KiB peak resident memory. No Stage 2
checkpoint was emitted. The log establishes the exact boundary:

```text
alumacc: created 54,777 $alu and 6,974 $macc cells
share:   SAT-based resource sharing started
<killed>
```

`share` is an optimization, not a legality requirement. The next proposed scout
split checkpoints immediately after comparator mapping plus `alumacc`, omits
`share`, and then continues with `opt`, `memory -nomap`, `opt_clean`, and Xilinx
memory mapping. Omitting `share` yields a conservative resource estimate and
must be recorded in every resulting utilization report.

## Share-free Xilinx mapping result

- Status: partial result accepted; full LUT cover and nextpnr blocked by host memory
- Updated: 2026-07-14

The full `opt` pass and the standard `memory -nomap` pipeline each exceeded the
30 GiB host limit, so the accepted staged flow omits `share`, `opt_merge`,
`opt_muxtree`, and memory-priority/share analyses. It performs the successful
subpasses only: `opt_expr`, `opt_clean`, `memory_collect`, Xilinx memory-library
mapping, direct `memory_map`, `maccmap -unmap`, isolated DSP mapping, isolated
ALU/LCU mapping, and isolated register mapping.

This is a legal, deliberately conservative mapping frontier rather than an
optimized implementation. The large model memories remain external to
`main_1`; only 11,746 bits of Calyx control-local memories were mapped, all to
flip-flops. No BRAM or LUTRAM was inferred.

| Mapped resource | Measured count | XC7K480T capacity | Provisional utilization |
|---|---:|---:|---:|
| DSP48E1 | 2,310 | 1,920 | 120.3% |
| CARRY4 | 392,183 | 74,650 slices / carry sites | 525.4% |
| FDRE + FDCE + FDPE | 193,582 | 597,200 flip-flops | 32.4% |
| RAMB36E1 | 0 | 955 | 0% |
| LUTRAM | 0 | device-dependent SLICEM capacity | 0% |

The CARRY4 comparison is a structural capacity check: a 7-series slice provides
one CARRY4 site. It is not a substitute for a final packed LUT count. The
2,310-DSP count required `maccmap -unmap` before `map_dsp`, because the staged
flow had already converted multiply/add arithmetic to `$macc_v2` cells before
the usual Xilinx DSP-recognition phase.

The later Boolean mapping checkpoint contained 27,933,076 cells, including
15,020,217 `$_OR_`, 4,815,186 `$_XOR_`, 2,327,730 `$_AND_`, and 1,419,259
`$_MUX_` cells. It was 7.3 GiB on disk. A read-only Yosys parse of that
checkpoint drove the host into heavy swapping (5 GiB of the 8 GiB swap in use)
before LUT covering could start. It was deliberately interrupted; no artifact
was lost.

Therefore no legal fully LUT-covered Xilinx JSON exists yet, and nextpnr-xilinx
cannot provide a place-and-route utilization report on this host. The nextpnr
frontier is host memory during LUT covering, not a confirmed nextpnr tool bug.
Those pre-mapping counts are a structural diagnostic, not a final mapped utilization result. The Task 3 pinned mapping route is the authoritative utilization experiment for this W8A8 Calyx kernel. The 2026-07-14 run recorded a native-SV generation frontier before RTLIL/Yosys, so FPGA fit remains unresolved.
