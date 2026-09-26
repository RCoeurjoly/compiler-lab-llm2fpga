# RC decode-8 implementation-gate diagnostic

Status: implementation gate stopped at Yosys timeout; no P&R or bitstream
claim.

The input is the canonical compiler-generated W4A8 Representative Core
decode-8 snapshot, whose decompressed SystemVerilog SHA-256 is
`62255f24c12c11b699c972b824fb2cb4119d94f733d57124117b9c00a5e18fa6`. The
synthesis frontend normalizer completed and produced normalized-SV SHA-256
`156a23f93b3ccff8a80ef49c2c08fe5b4cbf29329aa9ac2f91d9b2410748f08b`.

The Nix evidence derivation completed with durable output after the flow fixes
in commits `1e15681`, `1311e6a`, `32326e2`, and `5f22297`:

- the diagnostic XDC is materialized inside the derivation;
- canonical gzip snapshots and local scripts are rematerialized under fresh
  store names, avoiding stale zero-byte Nix paths;
- Yosys and nextpnr each have a 600-second bound;
- the receipt survives a tool timeout.

Observed result:

```text
yosys-status.txt: 124
nextpnr-status.txt: not-run: Yosys mapped JSON was unavailable
fit: undetermined
timing: unavailable
```

The bounded run therefore establishes a current implementation bottleneck in
Yosys on this generated phase, before mapping or placement. It does not
invalidate the previously recorded bit-exact compiler/RTL simulation result,
and it does not claim PCIe, DDR3, bitstream, or board inference.

## Pass-localization experiments

Two temporary replays used the exact normalized source and the same synthesis
script:

1. Removing only the explicit post-techmap `alumacc` pass still timed out
   after 700 seconds, during the following optimizer work on about 406,000
   cells.
2. Removing both post-techmap `alumacc` and `opt` progressed farther, into
   Xilinx memory library mapping, but also timed out at 700 seconds.

Therefore no single post-techmap pass is yet proven to be the sole blocker.
The evidence points to the representation/scale of the generated netlist and
the later memory-mapping stage. These experiments remain diagnostic; no
semantics-changing pass omission has been adopted as a production flow.

A bounded pre-memory-map replay completed in about eleven minutes and
captured the first Xilinx-mapped statistics before the expensive memory
library pass. The top module contained 313,593 cells, 1,241 memories,
101,931 mux cells, 68,971 OR cells, and 266 DSP48E1 cells. This confirms that
the dominant cost is the compiler-generated control/data representation, not
PCIe or DDR3 integration. The temporary JSON backend probe itself stopped on
an FDCE primitive-process limitation; the statistics remain valid because they
were emitted before that probe.

A third replay passed `-nobram` to the final `synth_xilinx -run
map_memory:` stage. It also timed out at 700 seconds, this time while
entering `MEMORY_LIBMAP` for LUTRAM-only legalization. Disabling BRAM
selection is therefore not a sufficient workaround; the mapping cost is
driven by the number and shape of generated memories, not one physical-memory
family.

A fourth replay restricted `memory_libmap` to the Xilinx LUTRAM library only
(with the BRAM library and its candidates removed). It still timed out at 700
seconds while entering `MEMORY_LIBMAP`. Candidate-library breadth is therefore
not the primary cause; reducing the number/shape of memories before Yosys is
the next evidence-backed direction.

## Packed done-buffer normalization

The synthesis frontend now rewrites the six generated declarations of the
form `logic done_buf[1:0]` to `logic [1:0] done_buf`. Bit-select semantics are
unchanged, but the packed form prevents Yosys from importing each pipeline
pair as a separate memory. The focused frontend suite passes, and Yosys-Slang
AST elaboration of the transformed RC passes with zero errors and warnings.

The bounded synthesis replay still reaches `MEMORY_LIBMAP` and times out, so
this is a validated representation improvement but not yet a complete mapping
fix. Its transformation receipt reports `packed_done_buf_repairs: 6` and
output SHA-256
`6d095664c791bf2797b86c6d0f062a4087bc7fc7670404b5b130e3bfd44670b8`.

The packed pre-map replay quantified the effect: memories fell from 1,241 to
160, memory bits from 20,284 to 18,122, and cells from 313,593 to 308,188.
The remaining 160 memories correspond to the external RC memory ABI
(`$memrd_v2`/`$memwr_v2`: 160 each). The normalization therefore removed the
internal pipeline-state memories; the remaining implementation cost is now
concentrated in the intended external memories and their control logic.

## Global block-RAM mapping experiment (rejected)

As a bounded tool experiment, the packed normalized source was copied to a
temporary workspace and every generated `seq_mem_d1` declaration was given
`(* ram_style = "block" *)`. The production source and compiler contract were
not changed. The replay used the same Xilinx synthesis script, with the
post-techmap `alumacc` and `opt` omissions used by the preceding diagnostic
replays.

Yosys entered `MEMORY_LIBMAP` and honored the attribute, but then failed on
the generated memory `main.mem_128.mem` with:

```text
ERROR: no valid mapping found for memory main.mem_128.mem
```

This is evidence that a global block-RAM directive is not a valid legalization
strategy: at least one generated width/depth shape is incompatible with the
available Kintex-7 block-RAM templates. The experiment produced no mapped JSON,
so it did not reach nextpnr and changed no repository RTL. The next tool-level
direction is selective legalization (choose BRAM only for compatible shapes,
LUTRAM or reshaping for the rest) or compiler-side memory-shape consolidation.

## Selective memory-style pass (compiler-side candidate)

The new `annotate_compiler_memory_styles.py` pass implements that policy as an
auditable transformation rather than a global pragma. It annotates only
`seq_mem_d1` instances whose width is compatible with a 7-series BRAM mode,
whose depth is at least eight, and whose total storage is at least 256 bits.
Tiny or irregular memories remain unconstrained so Yosys can choose LUTRAM or
registers. On the packed decode-8 source this selects 31 of 165 instances and
leaves 134 unconstrained. The pass emits a SHA-256 receipt and has focused
unit coverage. Yosys-Slang elaboration of the transformed source completed with
zero errors and warnings. It is not yet wired into the production Nix gate;
that integration remains contingent on a bounded synthesis replay showing a
real mapping improvement.

The candidate was replayed with the redundant full `opt` immediately before
`map_dsp:coarse` removed (the required `opt -nodffe -nosdff` cleanup was kept).
That bounded 420-second run reached `SYNTH_XILINX`'s `MEMORY_LIBMAP` stage;
the previous run spent the whole bound in the optimizer. It still timed out
inside memory legalization and emitted no mapped JSON, so the change is
diagnostic rather than an accepted production-flow modification. The evidence
supports separating the optimizer and memory-library timeboxes and evaluating
the selective annotations with a longer, independently bounded mapping stage.

The selective pass was then extended to scalarize all 32 one-entry
`seq_mem_d1` instances (including the previously failing `8x1` shape) into a
same-ABI `seq_mem_d1_scalar` register implementation. Yosys-Slang elaboration
still passes with zero errors and warnings. The 420-second replay reached
`MEMORY_LIBMAP` but timed out at the same frontier, so one-entry memories are
not the dominant remaining cost. The scalarization remains a valid
representation cleanup; the unresolved blocker is the legalization of the
remaining multi-entry memories and the mapper's search over their shapes.

Finally, Yosys's `memory_libmap -no-auto-block` option was tested with the
correct pinned Series-7 library files and the same scalarized candidate. The
run still reached `MEMORY_LIBMAP` and timed out after 420 seconds, without a
mapped JSON. Disabling automatic block selection is therefore not a sufficient
tool fix; the production synthesis script remains unchanged.

### Replay-order correction and persistent checkpoint

The first selective replays above were run from the pre-packed temporary
source, so their mapping-frontier comparisons are not authoritative for the
production candidate. They are retained only as diagnostic tool experiments.
The corrected order is: frontend normalization (including packed `done_buf`),
then selective style/scalar legalization. That source elaborates cleanly and
its pre-memory-map flow completed in 417 seconds, writing a 594 MiB RTLIL
checkpoint. Mapping that checkpoint independently still timed out in
`MEMORY_LIBMAP` after 420 seconds while enumerating LUTRAM candidates.

An explicit-only diagnostic (`-no-auto-block -no-auto-distributed`) completed
memory lowering quickly, but produced 522,890 generic cells and no usable
implementation result; it is a resource-explosion fallback, not an accepted
flow. The checkpoint establishes the next fast-iteration boundary: future
Yosys mapping/tool patches can be evaluated without repeating the 417-second
front half.

The persisted-checkpoint inspection adds an important Yosys detail: with
`-no-auto-block -no-auto-distributed`, `memory_libmap` completes in about
nine seconds, but leaves 90 `$mem_v2` memories and emits no BRAM/LUTRAM cells.
The earlier Verilog `ram_style` annotations are not preserved as actionable
placement metadata after `memory -nomap`/memory collection. Therefore a
production fix must reattach placement intent at the RTLIL `$mem_v2` stage (or
teach Yosys to classify those memories by width/depth); adding more source
attributes alone will not constrain the mapper.

Lowering the remaining memories immediately with `memory_map` is only a
diagnostic fallback: it completes quickly but produces 522,890 generic cells,
far beyond a useful Kintex-7 implementation. No bitstream or P&R claim is
made from that fallback.

## Memory-shape legality correction

A direct RTLIL probe forced one representative `32x8` memory to BRAM and
failed immediately with `no valid mapping found`. The pinned Series-7 memory
library does not accept these shallow address geometries as block RAM. The
candidate pass therefore no longer forces shallow memories to BRAM: it
scalarizes one-entry memories and pads all other shallow `seq_mem_d1`
instances to 32 entries with 5-bit addresses, a legal LUTRAM geometry. This
adds 131 padding repairs to the packed decode-8 source; Yosys-Slang elaboration
passes with zero errors and zero warnings.

The first full 600-second replay of this padded source timed out in generic
comparator techmapping before `MEMORY_LIBMAP`, so the policy is not yet a
production-flow change. It remains an evidence-backed compiler candidate to
evaluate from the persistent pre-map checkpoint, with the packed baseline
preserved.

The padded candidate's pre-map flow completed in 421 seconds and produced a
583 MiB RTLIL checkpoint. Independent mapping then selected the Xilinx LUTRAM
template for many memories (for example `main.mem_81.mem` through
`main.mem_147.mem`) but still timed out after 420 seconds while processing the
remaining candidates. This confirms the shape repair removes the immediate
legality failure; the unresolved issue is the global mapper's search/runtime,
not an invalid LUTRAM geometry.

## Deterministic batched mapping and implementation probe

The padded RTLIL checkpoint was mapped in deterministic two-cell batches,
avoiding the global `MEMORY_LIBMAP` search. The first 40 memories mapped in
265 seconds; the remaining 50 mapped from that checkpoint in 329 seconds.
After primitive techmapping, the complete netlist contained 273 `RAM32M`
LUTRAM primitives and 266 `DSP48E1` cells. Selected-top JSON serialization
succeeded, providing a valid nextpnr input artifact.

Constrained nextpnr then reached packing (including all 266 DSPs and the four
diagnostic I/O ports) but terminated before placement/routing, producing no
FASM or timing report. This is an implementation-scale/resource failure, not a
functional or memory-legality failure. The batched mapper and checkpoint are
diagnostic infrastructure; the production Nix gate remains unchanged until
the batch schedule and netlist size are independently qualified.

### Exact implementation failure and bounded legalization probe

The authoritative nextpnr log gives the first concrete implementation error:

```text
ERROR: Unable to place cell '$100', no Bels remaining of type '$logic_and'
```

It reports 2,184 `SLICE_LUTX` and 266 `DSP48E1` cells before this error, and
produces no FASM or timing report. The selected JSON therefore still crosses
the nextpnr boundary with generic logic cells; this is an incomplete
technology-mapping boundary, not evidence that the RC has exhausted the
Kintex-7 LUT fabric. A bounded attempt to apply Yosys's generic `techmap.v`
to the 814 MiB selected JSON exited without producing a replacement artifact.
That failed experiment is diagnostic only; the production Nix flow is
unchanged.

A second bounded replay started the standard Xilinx `fine:map_cells` sequence
from the persistent 584 MiB RTLIL checkpoint. It stopped during the initial
optimizer and produced neither JSON nor a placement artifact. Thus the
standard post-memory mapping stages cannot yet be evaluated on the complete
checkpoint within the current host/timebox; a smaller extracted module is
needed for the next tool experiment. This does not alter the RC semantics or
the production flow.

Two additional bounded probes refined that frontier. Direct `abc -fast -lut 6`
on the persistent checkpoint completed in about 25 seconds, but extracted
zero gates because the checkpoint still consisted of coarse operators. A
preceding `simplemap` expanded the design and reached ABC, but emitted no
checkpoint within the bound. The complete RC therefore needs a partitioned
coarse-to-gate mapping boundary; invoking the generic expansion on the
monolithic checkpoint is not a viable iteration loop.

### Emission hierarchy probe

The generated SV contains one large compiler component (`main_1`) wrapped by
`main`, alongside reusable primitive-library modules. A bounded Yosys probe
that selected `main_1` as the top still elaborated the complete source and
stopped at the frontend's deep-AST-recursion warning before writing RTLIL.
This rules out post-hoc nextpnr selection as the immediate partitioning fix:
the useful compute hierarchy has already been emitted as one monolithic
component. A fast implementation loop therefore requires a compiler/Calyx
emission boundary (or a mechanically generated component split) before Yosys
technology mapping; no handwritten or kev-gpt RTL is introduced.

## Wrapped-main staged implementation probe

The previous `main_1` probe was the wrong implementation top for a board-facing
closure test: it deliberately exposed every compiler memory port and therefore
presented 6,441 top-level bits to nextpnr. The compiler-generated `main`
wrapper has the intended four-port shell (`clk`, `reset`, `go`, and `done`) and
keeps the `main_1` memory interface internal. This is still the exact
compiler-generated source, not a handwritten or kev-gpt-derived replacement.

Using the pinned `yosys-slang` frontend on the source (SHA-256
`1b89366a72356ee92da4e4e8fe71d6376d35622296c131b4a4b574a8f305df65`) with
`--top main` completed with zero errors and zero warnings in 2.8 seconds. The
post-frontend RTLIL contains 24,269 cells. A bounded no-FSM preparation
completed in 5.9 seconds and produced 13,480 cells; FSM extraction remains
omitted as a diagnostic fast path because it was the earlier synthesis
blow-up.

The staged Xilinx mapping then completed as follows:

| checkpoint | result |
| --- | --- |
| coarse | no DSPs for this integer RC; 13,480 cells |
| fine | 38 CARRY4, 26,663 cells |
| ABC + Xilinx LUT/FF legalization | 948 FDRE, 1,452 LUT2, 931 LUT3, 913 LUT4, 667 LUT5, 974 LUT6, 38 CARRY4 |

The final mapped JSON before metadata legalization has SHA-256
`5f40972e38a9aac0b5351a637cce20ac4e1f34ff65b3631013a6aa7d0f034e21`. The
pinned nextpnr frontend requires explicit `port_directions` for generated
primitive cells. Adding those directions mechanically (without changing
connections, parameters, or logic) yields JSON SHA-256
`572dbc7d6992d77eb17416f1d3fbbe5b544df83930aaf9ffaf46fde8686cbbad`.

With the four-port probe XDC, nextpnr passed packing, placement, global-clock
routing, and main routing, and emitted a diagnostic FASM. The bounded host
observation ended during post-routing legalisation rather than capturing the
process's final success marker; the FASM and completed routing/timing records
are therefore implementation evidence, not yet a reproducible qualified
Nix gate. The diagnostic FASM is SHA-256
`8c9c1cd4de1eec3dbcfc5a1b323106a6903dcb8542a2c7abf2f17a4d7de8945a`.
The final critical-path report is 91.15 MHz (PASS at the 12 MHz probe target);
the reported path is 1.6 ns logic plus 9.4 ns routing. This is an
implementation/fit probe only: it uses the four-port diagnostic XDC, not the
YPCB PCIe/DDR3 top, and does not establish functional simulation, PCIe ingress,
DDR3 calibration, or board inference. The first nextpnr issue has therefore
progressed from missing DSP directions and an invalid memory-heavy top to a
closed, routed compiler-generated RC diagnostic image, pending a durable
terminal-success receipt.

### Existing Nix-qualified RC route receipt

The project’s existing Nix attribute
`tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-xc7k480t-nextpnr-utilization`
has now been inspected directly in the store. Its route receipt reports
`status: success`, `exit_status: 0`, and a nonempty FASM. This is the durable
checkpoint to use instead of the transient `/tmp` replay above:

* mapped JSON SHA-256: `4e82c669582eaa84d114ddccdc966ba635a471fea5d6793ce2c28bc90613cf9c`;
* FASM SHA-256: `2d97aeb06ef3481ad70058362a706f71e6664129ed53bca42fd48ca0dd250db3`;
* route receipt SHA-256: `7bd3fa32ba7ca7302c627093b589f9a6118107e3fed08d80f5e6dea108b9e0ee`;
* nextpnr log SHA-256: `67d3359f30e07be93423421900077f93a9fa351b25a3cce04013fdb56c38cbb1`;
* final reported frequency: 102.44 MHz at the 12 MHz probe target;
* routed utilization: 5,200 LUTX, 645 FF, 38 CARRY4, zero DSP and zero BRAM.

This proves a reproducible compiler-generated RC implementation route under
the diagnostic four-port XDC. It is not yet the requested YPCB PCIe+UberDDR3
design: the artifact has no PCIe endpoint, no UberDDR3 controller, and no
board inference evidence. The next gate is therefore functional transaction-
level RC equivalence followed by integration with the existing platform, not
another generic Yosys/nextpnr experiment.

### Existing compiler RC semantic-equivalence receipt

The realized Nix package
`tinystories-representative-core-w4a8-integer-sv-equivalence` provides the
transaction-level semantic gate for the same compiler-generated integer RC.
Its report status is `pass`: 51 tensor inputs are bound, 83 RTL memories are
initialized from the authenticated image, the simulation completes in
0.04995 seconds, and the output bytes are `fe4c`, corresponding to PyTorch
INT8 output `[-2, 76]`. The expected and simulated output hashes both equal
`8ab4cc3ce350de3e4d1da6136c6c0fd0d4f94f34e8fb82a8ee4eb80a3e9746ee`.
This establishes the RC's current compiler-generated simulation equivalence;
it is not yet autoregressive generation and does not exercise PCIe or DDR3.

### Fresh Nix revalidation of the integrated PyTorch contract (2026-09-26)

The integrated export was rebuilt from the current flake rather than relying
on the older store path.  The fresh derivation is
`/nix/store/4fh14bw446l1ngvjhb905vl98jrclalp-tinystories-w4a8-rc-serving-integrated-pytorch-exported`.
Its receipt records one integrated exported program, 18 output tensors,
`frozen_phase_qparams_equal=true`, `frozen_prefill_equal=true`, and
`save_reload_equal=true`.  The cache-chained observation remains the
three-stage contract `prefill-8 -> decode-8 -> decode-9` with token sequence
`[0, 0, 4]`; the source model is the pinned TinyStories-1M snapshot.  The
fresh hashes are:

| artifact | SHA-256 |
| --- | --- |
| `exported.pt2` | `03cec6bc7857ac7184fb5c63b53565c36228245474ed2f6299670e7ef33fded9` |
| `observation.json` | `3a318cc316848d8865fb013b7c9573b432218e99f8595d0af28725cf253d2da1` |
| `readback-manifest.json` | `e8708c8692c48721153cff1381db3cc6054abd9e32aa8965235dd905b81dd298` |

This revalidation changes no RTL or transport.  It freezes the exact
compiler input and phase/cache contract that the next compiler-side
partitioning work must preserve.

### Flat-SCF phase-boundary measurement (2026-09-26)

The current integrated compiler artifact
`/nix/store/jcrilmvr5m4gnynd9ib57qkdp20ydn8x-tinystories-w4a8-rc-serving-integrated-flat-scf/flat.scf.mlir`
contains one `func.func @main`, 74 memref arguments, 1,711 `scf` loop/branch
operations, and no `func.call`, phase-named operation, or cache-phase symbol.
The three phases are therefore represented as straight-line regions inside a
single flattened function before Calyx emission.  This is the direct evidence
for the current implementation bottleneck: the next compiler transformation
must recover explicit prefill/decode component boundaries (including the
four-leaf cache ABI) before generic Calyx/Yosys lowering, while preserving the
fresh export contract above.

The corresponding Nix-provided Python contract gate was rerun with
`unittest`: 21 tests passed and 2 tests were intentionally skipped.  This
covers the cache ABI, phase ordering, integrated observation/readback
manifest, and export save/reload behavior; it does not claim generated-RTL,
PCIe, DDR3, or board success.

### Fresh compiler-generated decode-8 RTL gate (2026-09-26)

The missing phase artifact was rebuilt through the pinned pipeline and
simulated against its fresh exported-program reference.  The Nix outputs are:

* SV: `/nix/store/qvymxdvl9896q0x3xibcqqvdqc92grfb-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-calyx-native-sv`
  (`main.sv` SHA-256
  `05dde596f14194bbbc5c67cdf71634b3adff93e310438d581c2f478ffeef354a`);
* flat-SCF: `/nix/store/29ysf5wv89bvifsk0pz971p6dx1cjys6-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-flat-scf`;
* exported program: `/nix/store/najg24bh3ff27a2s8159ml2sdlrk682h-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-pytorch-exported`.

`run_rc_serving_w4a8_sv.py` reports `status=pass`, bit-exact equality on all
five semantic output ports, maximum absolute error `0.0`, compilation time
129.98 seconds, and simulation time 297.07 seconds.  This is a
compiler-generated RTL phase gate; it is not yet the integrated multi-phase
program and does not exercise PCIe, DDR3, or hardware.

The Nix wiring, generated-shell, and XC7 phase-artifact regression tests also
pass (`21 tests`, `unittest`).  These tests retain the one-wholesale-integrated
program invariant and reject silently substituting a bundle of phase programs;
they are structural checks, not a claim that the integrated RTL has passed
simulation or implementation.

### Nested Calyx emission diagnostic (2026-09-26)

As a bounded tool experiment, the existing integrated Calyx artifact was sent
through the same backend with `CALYX_EMIT_NESTED=1` and a 900-second wall-time
bound.  CIRCT export completed (input Calyx-MLIR SHA-256
`46730cc190947b0e1c962b95c3c36d56f2c5d022f862753a43ee8951a549b1f6`; exported
Futil SHA-256 `980d3e36d8fcb0c4bf6e49388be20c20f1bea2f2feae2dc138203188421a1101`),
but Calyx timed out with exit 124 during its `cell-share` stage.  No SV was
emitted.  This diagnostic does not change the production flow; it shows that
enabling nested emission alone is not a bounded solution for the current
monolithic program.

A second bounded replay disabled only Calyx `cell-share` while retaining the
same generated Futil, non-nested emission, and 900-second bound.  It advanced
past `cell-share` (the log recorded `compile-invoke: 7198ms`) but still timed
out with exit 124 before SV emission.  Therefore `cell-share` is not the sole
blocker; the monolithic invoke/control representation remains the dominant
unbounded stage.  No production pass was changed.

A third bounded replay retained the same source and disabled optimization
passes with `CALYX_COMPILE_PASSES=no-opt`.  Calyx rejected this before SV
emission with its invariant that `repeat` statements must first be removed by
`compile-repeat` (panic in `top_down_compile_control.rs:212`).  This rules out
skipping all compile passes as a useful workaround; any further experiment
must retain repeat lowering and selectively bound the subsequent control
passes.

A fourth replay used the minimal legal pass set
`CALYX_COMPILE_PASSES=compile-repeat` (with `cell-share` disabled).  It did
not reach SV emission: Calyx rejected the resulting Futil with
`Malformed Structure: Control must be empty` at the generated `seq` block.
This confirms that the backend requires a coordinated control-lowering
sequence; removing the general pass set is not a safe shortcut.  No
production pass was changed.

### Integrated Futil control census (2026-09-26)

The retained compiler-generated Futil (`model.futil` SHA-256
`980d3e36d8fcb0c4bf6e49388be20c20f1bea2f2feae2dc138203188421a1101`) contains
764 `seq_mem_d1` memories, 10,157 registers, 10,932 groups, 3,091 `seq`
blocks, 1,829 `par` blocks, and 1,829 `repeat` loops.  The public component
has one `invoke` of `main_1`, whose generated control contains the repeated
phase/block schedule.  This census explains why `compile-invoke` remains the
frontier after cell sharing is disabled and provides the quantitative target
for a compiler-side control/memory consolidation pass.

A bounded direct Calyx replay disabled only `compile-invoke` (also disabling
cell sharing and verification).  It failed immediately in
`promotion_analysis.rs:95` with `Shouldn't Promote to Static if there is a
Comb Group`, before SV emission.  The generated invoke boundary is therefore
required by the current Calyx pipeline; removing it is not a valid workaround
for the integrated control frontier.

For pass-order localization, a short replay additionally disabled
`static-promotion` and `static-inference` along with `compile-invoke`.  Calyx
then stopped at `top_down_compile_control.rs:216`, reporting that `invoke`
statements must be compiled away before control lowering.  This confirms that
the invoke rewrite is a structural prerequisite independent of promotion
heuristics; the fix must make that rewrite tractable rather than bypass it.

### PCIe transport availability observation (2026-09-26)

At `2026-09-26T10:23:01+02:00`, the host enumerated the YPCB endpoint as
`0000:42:00.0`, Xilinx device `10ee:0480`, subsystem `10ee:abcd`, with BAR0
assigned at `0x74000000` (4 KiB).  This confirms that the established PCIe
lifecycle is currently available.  It does **not** identify the programmed
FPGA image and does not prove DDR3 calibration, image load/readback, or RC
inference; those remain separate acceptance gates.

### Compiler-RC plus PCIe/UberDDR3 integration route

The realized `compiler-ddr3-trace-replay-route` artifact
`/nix/store/kl9k5xp9xyajx7m6zhkcjdp2cg47x7hv-compiler-ddr3-trace-replay-route`
contains the compiler-generated RC under
`gen_compiler_command_adapter.gen_compiler_generated_rc`, integrated with the
PCIe and two-lane UberDDR3 shell. Its route log reports 24 warnings and zero
errors, emits `replay.fasm` (SHA-256
`a32c347c2dfaa269b35d9665293efe89ffa16c01a7de29e40eeaefc6327aa913`), and
completes routing.

This is the first durable implementation evidence for the actual integrated
architecture, but it is not timing-qualified: `pcie_user_clk` reaches 81.34
MHz against its 62.50 MHz requirement, while `rowstream_clk` reaches only
53.87 MHz against the fixed 83.33 MHz DDR3 requirement. The failing critical
path is in the integrated rowstream/DDR3 domain, not the PCIe clock. The
current next action is therefore a targeted rowstream timing diagnosis or
tool/constraint repair; PCIe and DDR3 must remain unchanged while isolating
that failure. No board programming or inference claim follows from this
route-only artifact.

### Passing integrated timing receipts already present in Nix

The store contains multiple legal routes of the same compiler-generated
PCIe+UberDDR3 shell. In particular:

* `qf0ps72f0fx4938cqdkw0dz1nrx69bxb-compiler-ddr3-trace-replay-route` reports
  `legal_route: true`, rowstream 100.47 MHz (required 83.333 MHz), and PCIe
  69.35 MHz (required 62.5 MHz).
* `2xb34ymsrmpjz71i0dhfrvxgp41qww0f-compiler-ddr3-trace-replay-route` reports
  `legal_route: true`, rowstream 88.48 MHz, and PCIe 95.26 MHz.

Both receipts explicitly scope timing to the pinned fabric model and do not
claim DDR/PHY, CDC, or electrical signoff. Their FASM hashes are respectively
`5b5babb95da42b3651eacf875276a94af41d70282d77001323d565ad8f8352e1` and
`57f38a9a6d3986e6075351c2b27ca856e4591630eac9ca894b2b55780c82422f`.
This changes the timing diagnosis: the integrated architecture can close at
the fixed profile, but the current route recipe is placement-sensitive. The
next reproducibility gate is to identify and pin the successful placement
inputs/seed and then carry that exact FASM through bitstream generation and
board validation.

### Bitstream conversion of a timing-passing integrated route

The qf0 route was converted with the pinned prjxray tools and Kintex-7
database.  The input FASM is the route artifact above (SHA-256
`5b5babb95da42b3651eacf875276a94af41d70282d77001323d565ad8f8352e1`).
Conversion completed with `fasm2frames` and `xc7frames2bit`; `bitread` then
decoded the result and reported `DONE` and 46,336 configuration frames.

The resulting host-only artifacts were:

* frames SHA-256: `a240215edcb0900541b688606fb8dc4b6825e24594569228cdb6f671118fada8`;
* bitstream SHA-256: `0718ebb99b270e3bc9cb58414cb8ad471948ccebcc5becce8c530c4f22972d48`;
* decoded configuration-bit listing SHA-256:
  `fa1b848244fd5c9fbc8a130dee43030b976f0ae9dae0970f058b45a3081734e9`;
* decoded listing: 880,384 nonempty lines.

The conversion used only pinned Nix-store fasm/prjxray/PyYAML/simplejson/
intervaltree/sortedcontainers paths and the database part file
`xc7k480tffg1156-1/part.yaml`.  This proves FASM-to-bitstream conversion and
structural decoding, not board programming, PCIe enumeration, DDR3
calibration, or inference.  The bitstream remains unprogrammed pending the
board gate and an independently reproducible route receipt.

The same frame stream is already present in the content-addressed Nix output
`/nix/store/2lla0fwzm7y2kn0y9wbljlwmd7vpmhmc-compiler-ddr3-trace-replay-bitstream`:
its `replay.frames` hash is the same `a240215e...fada8`, and its decoded
configuration hash is the same `fa1b8482...1734e9`.  Its bitstream hash is
`a6683622793ac1975de4615ca4bd8ee271fd74b0684080f7e579d2203e301690`.
The byte-level `.bit` hash differs from the `/tmp` conversion because the
container header is generated separately; the frame payload and decoded
configuration agree.  This Nix output is the preferred programming source
once the JTAG device is available.

### Autoregressive interface audit

The current compiler-generated Wishbone wrapper does not yet satisfy the
goal's autoregressive gate. `generate_tinystories_integer_wb_top.py` exposes
`token_data` as a two-entry local input memory and exposes `result0/result1` as
the two output bytes. `run_tinystories_integer_wb_sim.py` asserts `go` once,
waits for one `done`, and checks `16'h4cfe`; it does not feed a generated token
back into a subsequent invocation. Therefore the existing `pass` receipt is
one-shot semantic equivalence only. Multi-token feedback simulation, PCIe
image load/readback, DDR3 calibration/BIST, and board inference remain open
gates rather than being implied by the route or bitstream artifacts.

This audit must be read together with the separate stateful-serving RC
evidence, not as a claim that the compiler lacks a multi-token path.  The
durable receipt `docs/results/2026-08-14-w4a8-three-phase-equivalence.json`
reports `prefill-8 -> decode-8 -> decode-9` compiler-generated SystemVerilog
closures, all bit-exact against their frozen PT2E references (maximum absolute
error zero).  That serving profile has explicit cache/state phase boundaries
and is the appropriate compiler milestone for autoregressive simulation.  It
is distinct from the smaller integer diagnostic wrapper audited above.  The
three-phase receipt still does not prove PCIe ingress, UberDDR3 calibration,
FPGA fit for the integrated shell, or board inference; those remain the next
integration gates.

### Integrated-closure size profile

The compiler-emitted integrated closure is a single monolithic `main_1`
component: `sv/main.sv` is 50,901,558 bytes / 1,658,528 lines, with 8,097
sequential or combinational process blocks and approximately 63,229 generated
logic declarations.  The public shell is only a small wrapper; almost the
entire cost is inside `main_1`.  The Calyx source likewise contains one
top-level component with 382 external memories and no phase-named subcomponents.
This explains why simulator memory is exhausted before public-port execution
and identifies the next compiler boundary: preserve the phase/cache contract
but emit independently elaborable phase components or a compiler-generated
coordinator, rather than attempting another simulator flag on the monolith.

The integrated PyTorch export already provides the exact stateful target for
that partition: its authenticated observation records phase token IDs
`[0, 0, 4]` for `prefill-8`, `decode-8`, and `decode-9`, with 18 output regions
(three selected tokens, three logits vectors, and twelve cache leaves).  Its
receipt reports `frozen_phase_qparams_equal`, `frozen_prefill_equal`, and
`save_reload_equal` all true.  A partitioned compiler emission can therefore
be checked against a concrete token/cache contract; it must not invent a new
sequence or reuse reference RTL.

### Alternate-simulator probe for the integrated stateful closure

As a bounded diagnostic, Icarus Verilog 12.0 was run against the exact
compiler-generated integrated shell and closure.  The raw source first hit a
duplicate `sqrtOpOut` declaration and then exhausted memory at approximately
872 MiB RSS.  Applying the pinned synthesis-front-end normalizer removed 8,057
assertion blocks, one duplicate square-root wire, one duplicate request
declaration, and six packed `done_buf` declarations (receipt SHA-256
`2cfccc9572b19be21da662f47908d9eeec589e2f3eed8edf9ac616d6f24d4544`).  The
normalized source still exhausted Icarus memory at approximately 867 MiB RSS,
before elaboration.  This rules out Icarus as a low-memory qualification path;
the integrated RTL runner remains an implementation/tooling bottleneck, not a
semantic mismatch.

The current wrapper was re-run through the pinned Verilator binary from the
Nix store using the content-addressed wrapper and compiler SV artifacts.  The
transaction-level Wishbone test completed with `WB_RC_PASS result=4cfe`;
Verilator compilation took 18.531 s and simulation took 0.051 s.  This is a
fresh confirmation of the one-shot RC semantic gate, not a multi-token or
autoregressive result.
