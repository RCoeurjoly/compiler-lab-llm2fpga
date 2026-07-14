# W8A8 Calyx Task 3 Utilization Design

## Objective

Produce a reproducible, provisional Xilinx 7-series LUT, FF, DSP, and BRAM
estimate for the full TinyStories PT2E W8A8 route:

```text
PyTorch PT2E W8A8 -> Torch-MLIR -> TOSA -> Linalg -> SCF -> Calyx -> SV
-> exact Task 3-style Xilinx synthesis -> utilization report
```

The target is the Calyx `main_1` compute/control component. Its 2,133 logical
memories remain explicit external interfaces. This is an out-of-context kernel
estimate, comparable in intent to Task 3's large-memory-blackboxed F32 report;
it is not a DDR3 controller, a complete board system, or
functional-equivalence evidence.

## Evidence and root cause

The width-correct `main_1` checkpoint is 1.9 GiB and contains 3,106,002
generic RTLIL cells. It has no processes, but it is a single module. The
ordinary Xilinx flow reaches `share` in its `coarse` stage and is killed near
the 30 GiB host-memory limit. A later manual Boolean lowering expanded the
single module to 27.9 million primitive cells before LUT covering.

The historical Task 3 F32 report proves that the project can produce this type
of mapped estimate, but it used a separately pinned Yosys toolchain and a
different Handshake-derived netlist shape. Its result cannot by itself prove
that a monolithic Calyx netlist will map on this host.

Therefore the problem to solve is bounded technology mapping of a semantically
unchanged W8A8 kernel, not a new quantization, memory, or lowering change.

## Options considered

1. Reuse the exact Task 3 synthesis closure, including its staged RTLIL
   checkpoints, Xilinx mapping sequence, utilization writer, and pinned Task 3
   Yosys. This is the selected approach.
2. Use the current root-flake port of the Task 3 stage commands. It is a useful
   compatibility probe, but it is not a replacement for the historical pinned
   closure. On the exact W8A8 `main_1` checkpoint, Stage 1 completed and the
   verbatim Stage-2 `coarse:map_memory` command was killed in `share` at the
   host memory limit.
3. Recover hierarchy after `proc` and map partitioned modules. This remains a
   fallback only if the exact Task 3 closure also reaches a demonstrated OOM
   frontier.

## Selected design

### Primary path: exact Task 3 reuse

The first implementation reuses the Task 3 machinery rather than replacing it:

1. Expose a minimal Task-3-pinned Yosys execution boundary without entering its
   whole development shell, which otherwise pulls unrelated nextpnr inputs.
2. Feed the unchanged Calyx-emitted W8A8 SV through the Task 3 SV-to-RTLIL
   import boundary, selecting `main_1` as the out-of-context top. The adapter
   may generate only the wrapper required by the Task 3 helper interface; it
   must not rewrite model logic, memory ports, or arithmetic.
3. Run the Task 3 stages in their original order: `begin:prepare`,
   `coarse:map_memory`, targeted memory mapping, fine arithmetic/cell mapping,
   flip-flop mapping, ABC/LUT mapping, JSON emission, and the existing
   XC7K480T utilization writer.
4. Preserve a checkpoint and concise stage report at every Task 3 boundary.
   The first terminal frontier is evidence; no pass is skipped or reordered
   merely to advance past it.

The historical F32 report was generated through this family of stages and is
the correct reference for methodology. It is a saved result rather than a live
reproduction on the current host, so the W8A8 report must record the exact
pinned tool identity used.

### OOM expectation and contingency

There is a real risk of OOM: the current Yosys 0.66 reproduction of Task 3
Stage 2 reached `share` after creating 54,777 `$alu` and 6,974 `$macc`
cells, then was killed near the 30 GiB host limit. That observation is not
evidence that the Task 3-pinned closure will fail identically, because its
Yosys source and package are different.

Only if the exact Task 3 attempt records the same or a later OOM boundary does
the fallback activate. The fallback creates `submod -hidden` hierarchy from the
unchanged post-`proc` netlist, using deterministic 32,768-cell
declaration-order partitions, and then reuses the same Task 3 mapping/report
stages. Any resulting report is labelled **partitioned, conservative,
out-of-context estimate** because cross-partition optimization is limited.

### Boundary, reporting, and disk policy

Both paths target the original `main_1` interface: 12,802 ports and 115,933
port bits, including the 2,133 logical external memories. Neither is a DDR3
controller, a complete board system, or functional-equivalence evidence.

The report records the route, top, pinned tool identity, every completed Task 3
stage, original interface size, and the external-memory boundary. A fallback
report additionally records its partition limit and count. No W8A8-versus-F32
reduction factor is claimed until both reports have a comparable mapping
boundary and methodology.

Only compact reports and manifests are normal build outputs. Giant temporary
RTLIL and JSON artifacts stay in the build sandbox and are discarded after the
report is calculated. The exact `main_1` checkpoint remains independently
cacheable so a failed technology-mapping attempt does not require another SV
import and `proc` run.

## Verification

Tests precede implementation. They first assert that the W8A8 package selects
the Task 3 stage constructor and pinned Yosys boundary rather than the current
root-only equivalent. A tiny RTLIL fixture covers the fallback only: it must
show that the partition-script generator is deterministic, assigns every
selected cell once, and leaves the top ports unchanged after `submod -hidden`.

The full build must additionally verify:

- exactly one `main_1` top exists before and after Task 3 import;
- `done` remains a top-level output;
- the existing 12,802-port / 115,933-port-bit external-memory boundary remains
  unchanged;
- the original Task 3 stage order is recorded, or the first exception/failure
  is recorded explicitly;
- final utilization is derived only from a valid mapped Xilinx JSON; and
- all compact evidence identifies failure stage and peak/resource frontier if
  mapping does not finish.

Success is a compact XC7K480T report containing LUT, FF, DSP48E1, and
BRAM36-equivalent counts. A mapped report is sufficient for this milestone;
nextpnr placement, board integration, SmoothQuant, and numerical equivalence
remain deferred.
