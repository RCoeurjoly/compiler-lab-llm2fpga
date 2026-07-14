# W8A8 Calyx Partitioned Utilization Design

## Objective

Produce a reproducible, provisional Xilinx 7-series LUT, FF, DSP, and BRAM
estimate for the full TinyStories PT2E W8A8 route:

```text
PyTorch PT2E W8A8 -> Torch-MLIR -> TOSA -> Linalg -> SCF -> Calyx -> SV
-> exact main_1 RTLIL -> partitioned Xilinx synthesis -> utilization report
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

1. Run the current monolithic Xilinx flow unchanged. This is the cleanest
   methodology, but it reproducibly exhausts host memory in `share`.
2. Rebuild and use the historical Task 3 Yosys environment. This is useful as
   a later compatibility experiment, but currently requires substantial
   historical dependency fetching/building and is unsuitable on the nearly
   full disk.
3. Recover hierarchy after `proc`, then run normal Xilinx synthesis over the
   resulting modules. This preserves the W8A8 logic while bounding per-module
   optimization and is the selected approach.

## Selected design

### Partition construction

A small streaming helper will derive a Yosys command script from the exact
post-`proc` `main_1` RTLIL. It deterministically groups cell declarations in
their RTLIL declaration order into fixed-size partitions and tags each group
with Yosys's `submod` attribute. Declaration order is used because the imported
SV source location is not useful: essentially all cells carry the same
`main.sv:98160` elaboration location.

The initial fixed size is 32,768 cells per partition. A failed run records that
limit and its frontier; it must not silently change the partition size, since
that changes the conservatism of the resulting estimate.

The synthesis command will then:

1. Read the exact `main_1` checkpoint and assert its `done` port and recorded
   interface width.
2. Map only the small, internal Calyx control memories, run `proc` again if
   memory mapping creates processes, and assert that no process or memory
   objects remain before hierarchy recovery.
3. Apply the generated cell tags and run `submod -hidden` to make one
   semantically equivalent hierarchy from the former monolithic module.
4. Assert that `main_1/done` and every original top-level port remain present.
5. Run the ordinary `synth_xilinx -family xc7 -top main_1 -noiopad` flow
   without `-flatten`, then write a mapped JSON only long enough to derive the
   compact utilization report.

`submod -hidden` only changes representation: it moves tagged cells into
modules and connects them through generated private ports. It neither removes
logic nor substitutes any behavior.

### Conservatism policy

Partition boundaries prevent some cross-boundary optimization. The resulting
counts are consequently labelled **partitioned, conservative, out-of-context
estimate**. They must not be described as a post-place-and-route result or as
the exact cost of a DDR3-integrated accelerator.

The report will retain the route, top, partition cell limit, partition count,
original interface size, memory boundary, tool identity, and every successful
synthesis stage. It will also explicitly state whether a final mapped JSON was
obtained. No claim of a W8A8-versus-F32 reduction factor will be made until both
routes have a comparable mapping boundary and methodology.

### Disk and restart behavior

The implementation keeps only compact reports and manifests as normal build
outputs. Giant temporary RTLIL and JSON files stay in the build sandbox and are
discarded after the report is calculated. The initial exact kernel checkpoint is
an independently cacheable boundary so a failed technology-mapping attempt does
not require another SystemVerilog import and `proc` run.

## Verification

Tests precede implementation and cover a tiny RTLIL fixture. They must show
that the partition-script generator is deterministic, assigns every selected
cell once, and leaves the top ports unchanged after `submod -hidden`.

The full build must additionally verify:

- exactly one `main_1` top exists before and after partitioning;
- `done` remains a top-level output;
- the existing 12,802-port / 115,933-port-bit external-memory boundary remains
  unchanged;
- no processes or memories remain at the point `submod` runs;
- final utilization is derived only from a valid mapped Xilinx JSON; and
- all compact evidence identifies failure stage and peak/resource frontier if
  mapping does not finish.

Success is a compact XC7K480T report containing LUT, FF, DSP48E1, and
BRAM36-equivalent counts. A mapped report is sufficient for this milestone;
nextpnr placement, board integration, SmoothQuant, and numerical equivalence
remain deferred.
