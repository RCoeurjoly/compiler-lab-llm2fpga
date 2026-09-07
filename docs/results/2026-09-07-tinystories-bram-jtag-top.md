# TinyStories-1M BRAM/JTAG top integration checkpoint

This checkpoint replaces the autonomous timing shell with a board-facing
control boundary. The generated production `main` component now exposes:

| Signal | Direction | Meaning |
| --- | --- | --- |
| `clk`, `reset`, `start`, `valid` | input | compiler-kernel control |
| `token_index` | input | selects token slot 0 or 1 |
| `token_id` | output | selected committed token |
| `done` | output | completion of the two-token run |

`rtl/tinystories_1m_jtag_csr.sv` defines the YPCB JTAG CSR transaction:

- command `1`: write one prompt word (`command[5:4]`, `command[15:0]`);
- command `2`: reset the run state and start the kernel;
- command `3`: read status;
- command `4`: select/read token slot (`command[0]`);
- command `5`: pulse kernel reset.

The four prompt words are now driven from the CSR shadow registers into the
generated prompt-loading schedule. The board therefore loads the prompt before
the start command; no host-side token or intermediate-state feedback is used.

The production LM head now consumes each vocabulary-row GEMV result directly
from its 64-bit accumulator register during argmax. It no longer materializes
the 50,257-entry `lm_accumulator_i64` BRAM. The generated structural checkpoint
therefore falls from 39.3 Mbits / 144 memories to 36.1 Mbits / 143 memories,
without changing the signed-64-bit arithmetic contract. This is a capacity
optimization, not yet a fit result.

The authenticated Q8.24 token-embedding scales are a further exact capacity
optimization. Their values range from 14,525 to 105,952 and therefore fit in
signed 32 bits; the generated top stores the 50,257-entry table at 32 bits and
sign-extends each value to the existing signed 64-bit multiply before use (in
both embedding and logit scaling). The resulting Futil memory inventory is
97 memories / 34,448,640 bits (down from 36.1 Mbits), below the approximately
35.2-Mbit YPCB RAMB36-equivalent budget. This is a structural capacity result,
not a mapped-resource, timing, bitstream, or board-inference claim. Its
provenance receipt is `artifacts/reference/tinystories-1m-bram-scale-width-receipt.json`.
The later 16K-depth physical-bank experiment supersedes this earlier inventory
for synthesis mapping; the scale-width receipt remains a valid record of the
independent 32-bit arithmetic-contract reduction.

`scripts/pipeline/prepare_tinystories_1m_bram_image.py` now converts the
runtime-plusarg memory image into synthesis-visible static `$readmemh` inputs
and emits a hash manifest. The resulting SV was accepted by yosys-slang with
initialization enabled; the retained receipt is
`artifacts/reference/tinystories-1m-bram-static-image-receipt.json`. This is
image readiness only: the receipt intentionally does not claim a bitstream.

A bounded RAMB18/LUTRAM mapping experiment marked only the two largest MLP
weight memories as distributed and invoked the pinned `synth_xilinx` memory
stage. It did not emit a mapped report within the interactive observation
window and was terminated; no resource or timing claim is attached to that
experiment. The production RTL remains unchanged by it.

The banked static top passes the Yosys-Slang hierarchy/preparation gate at 242
memories and 35,158,330 structural memory bits. The corrected pinned
`synth_xilinx` coarse preparation completes in 311.86 seconds; the strict
map-memory result is 39 RAMB36E1 and 15 RAMB18E1 before final technology
mapping. The durable hashes and resource/placement diagnostics are in
`artifacts/reference/tinystories-1m-bram-production-synthesis-2026-09-07.json`.

The model weights remain immutable BRAM initialization data. The JTAG bridge
has been linted with Verilator in `BSCAN_SIM` mode, and the production
generated SV still passes Calyx compilation and the focused lowering tests.

## Banked-memory mapping checkpoint

The first coarse-to-memory-mapping attempt exposed the remaining capacity
problem: the vocabulary tables were represented as 50,257-word memories, and
the mapper left those memories unresolved. A focused mapper diagnostic then
showed that the installed XC7 BRAM rule set rejects the previous 32,768-word
bank shape. The compiler backend now preserves the exact flat tensor order
while using 256 vocabulary rows per code bank (197 banks of depth 16,384) and
four contiguous 16,384-word 32-bit scale banks. The code-table local address
is therefore 14 bits and the scale-table bank boundary is bit 14. Address
selection remains explicit in generated Calyx, including the corrected
per-level bank-bit selection; focused lowering tests pass and Calyx emits SV.
An exact reconstruction check at token rows 0, 1, 255, 256, 511, 512, and
50,256, plus scale-bank boundaries 0, 16,384, 32,768, and 50,256, passed for
the generated Futil hash
`1f1622d7bb917be662d5e51375b678f8431034f12fff1878792c02f77505a9b6`.
The strict coarse/map run must still be repeated for a hash-aligned resource
receipt, and this change is not yet a fit or timing result.

With that change, the regenerated static image has 242 structural memories
and 35,158,330 structural bits. The pinned XC7 coarse pass completed in
432.67 seconds and the following `map_memory` pass consumed all banked token
memories into 39 `RAMB36E1` and 15 `RAMB18E1` instances. Only three small
scratch `$mem_v2` memories remain (`prompt_words` and two done buffers).
The corrected design was then rerun end-to-end through Yosys-Slang, XC7
coarse synthesis, memory mapping, technology mapping, and JSON export. The
hash-aligned map again consumed the banked memories, and the generated JSON
reached nextpnr packing. After legalizing generic boolean cells, the design
requires 628,976 `SLICE_LUTX` sites against 597,200 on the Kintex-7 (105.3%),
with 21,976 FFs, 38 RAMB36E1, and 14 RAMB18E1. Placement therefore fails on
genuine LUT over-capacity rather than BRAM capacity. A diagnostic run with
`--ignore-loops` reached timing-budget annotation but did not place the full
design. A bounded ABC optimization attempt on the generated `main` module did
not produce an artifact within the observation window. This is therefore not
a placement or timing result. The hashes and
exact residual-memory list
are recorded in
`artifacts/reference/tinystories-1m-bram-production-synthesis-2026-09-07.json`.

The omitted DSP stage was also tested explicitly. Unmapping the coarse
`$macc_v2` cells enables Xilinx DSP inference, but produces 2,433 `DSP48E1`
instances against 1,920 available on the device. Thus DSP inference alone
does not rescue the design; it moves the over-capacity condition from LUTs to
DSPs. The bounded receipt records this as a diagnostic experiment.

A second bounded experiment applies `simplemap` only to the large boolean
operators in `main`, followed by `abc -lut 6`. It reduces the mapped main
module's `$and/$or/$xnor/$mux` counts from 12,029/3,770/2,867/1,798 to
4,292/70/1,868/20 and emits 20,801 LUT nodes. This is a promising compiler
optimization direction, but formal equivalence and a complete resource run
have not yet completed, so it remains a candidate artifact rather than an
accepted datapath change.

The generated full-top Verilator run did not reach completion in the observed
35 million-cycle window and was stopped to avoid an unbounded run. This is a
simulation-throughput blocker, not an inference result.

This is not yet a board-acceptance result. A real YPCB bitstream, timing report,
and three cold-start JTAG runs are still required before claiming board
inference. The bounded generated-SV execution was timeboxed at 90 seconds
without reaching completion, and the first full-top Yosys attempt did not
produce a report within the available synthesis budget. These are integration
blockers, not evidence of board inference or timing closure.

## Native primitive legalization checkpoint

The corrected 16K-bank image was rerun with the pinned Xilinx primitive
definitions instead of the temporary black-box primitive declarations. This
removed the earlier nextpnr BRAM port assertion: the mapper accepted 38
`RAMB36E1` and 14 `RAMB18E1` instances and proceeded into placement. A
selected arithmetic pass (`$alu`, `$lcu`, and `$macc_v2` only) also converted
the generated kernel arithmetic to 3,843 `CARRY4` cells without expanding the
whole design. The resulting placement attempt stopped on 38 residual generic
top-level `$alu` cells (`no Bels remaining of type '$lcu'` in the related
legalization path), before timing analysis. A full native Xilinx map was
bounded at 900 seconds and did not emit an artifact, so this is a compiler
iteration-time and legalization blocker, not a fit or timing result.

The temporary artifacts are retained under `/tmp/llm2fpga-banked-16384-image`:
`noshare-native-defs.json` is the primitive-definition control, and
`full-map3.json` records the selected arithmetic mapping. Neither is an
accepted bitstream.

The follow-up nextpnr run with direct ALU legalization reached packing and
reported 56,374 LUT sites, 4,899 CARRY4 sites, and the expected BRAM counts,
then stopped on 4,788 residual 128-bit `$fa` cells. A direct semantic
full-adder-to-CARRY4 experiment expands those cells to 157,986 CARRY4s,
exceeding the Kintex-7 capacity of 74,650. This rules out a mechanical
primitive substitution as the closure fix; the generated arithmetic must be
shared or serialized before a board bitstream is plausible.

## Production-only fixed-point width reduction

The compiler now has an opt-in `narrow_products` mode used only by the
production BRAM kernel. INT8×Q8.24 products are evaluated at 40 bits and the
following INT8 product at 48 bits, with explicit sign extension back to the
existing 64-bit accumulator boundary. The audit/reference generator remains
byte-identical; the focused test suite passes. The generated production SV
contains 14 40-bit and 7 48-bit multiply pipelines (versus 45 64-bit
pipelines in the prior production image). This is an evidence-backed
resource-reduction candidate, but its full hardware fit and exact board
inference are still unverified.

The first pinned coarse synthesis attempt on this candidate was bounded while
the global `share` pass was solving repeated SAT instances (for example,
2,750 cells / 13,549 variables / 35,034 clauses). It produced no mapped
artifact. This identifies global sharing as a separate iteration-time
blocker; future compiler passes must constrain or replace that sharing step
before another full-board attempt.

The YPCB top now marks the generated core hierarchy, token readback, and CSR
response as synthesis-preserved. This prevents a board build from silently
collapsing the accelerator to the LED shell when only status outputs are
observed. The focused top-integration tests pass; a new mapped resource result
is still pending.

A no-global-optimization control run (`techmap` + `alumacc` + `memory -nomap`,
without the broad `opt/share` sequence) completed in about one minute and
preserved 77,930 cells, including 333 `$alu`, 220 `$lcu`, 38 `$macc_v2`, and
279 memories. The subsequent BRAM mapper began processing the 197 token banks
but was bounded before completion. This gives a reproducible fast coarse stage
and identifies bank-by-bank memory mapping as the next bounded bottleneck.

The production SV runner now applies an idempotent
`(* ram_style = "block" *)` annotation to Calyx's shared sequential-memory
primitive. The annotation is synthesis-only and leaves RTL behavior and
immutable initialization unchanged. A direct check changes the generated
file from zero to one primitive-declaration annotation, covering all memory
instances. The bounded mapper then completed in 313 seconds and forced all
banked memories to Xilinx block RAM, producing 784 `RAMB36E1` plus 1,832
`RAMB18E1` (about 1,700 RAMB36-equivalents). This is within the Kintex-7
BRAM budget, but it is not yet a placement/timing result. The first nextpnr
attempt stopped before packing because the exported JSON did not carry the
same flattened primitive-module metadata as the known-good control
(`Failed to get direction for port ADDRARDADDR`). The next bounded task is to
repair that netlist packaging and rerun nextpnr; no board bitstream or
inference success is claimed.

The first full generated-SV run using the selective-memory artifact was
bounded at 900 seconds and terminated at 162,431,000 cycles without `done`.
It emitted an intermediate selected-token write of `0` at cycle 86,196,460,
not the expected `[11, 612]`. This is neither an inference pass nor a timing
result; it establishes that the current simulation path is too slow to serve
as an acceptance check and that its token writeback must be diagnosed before
hardware programming.

Comparing the mapped cell against the known-good primitive control identified
the immediate cause of the import failure: the new mapper emits a 17-bit
`ADDRARDADDR` connection on a `RAMB36E1`, while the legal Kintex-7 primitive
interface is 16 bits for this configuration. The control cell is 16 bits and
is accepted by nextpnr. Therefore the next fix must split or constrain the
oversized bank during memory legalization; trimming the address bit in the
RTL would be incorrect because it would alias model data.

The mapped-netlist experiment further shows that this extra bit is constant
`1` on both read and write address buses for every affected cell. Removing
that constant padding bit in a temporary JSON normalization does not yet make
nextpnr import the netlist, so the remaining failure is primitive/module
packaging rather than address semantics. The normalization is diagnostic only
and is not an accepted design change.

Re-emitting the mapped JSON through the known-good Xilinx sequence
(`cells_sim.v`/`cells_xtra.v`, flatten, process lowering, and cleanup) fixes
the primitive import problem. nextpnr then reaches placement and reports a
real legalization blocker: 220 generic `$lcu` cells remain, and one cannot be
placed because no BEL of that type remains. This confirms memory mapping and
primitive packaging are no longer the first blocker; the next compiler step
must legalize the generated carry/logic arithmetic before placement.

Applying the validated Xilinx arithmetic map (`techmap.v` plus
`xilinx/arith_map.v`) converts the 220 `$lcu` cells to 4,235 `CARRY4`
instances. nextpnr advances past the former `$lcu` placement failure, so this
is a confirmed critical-path improvement. A subsequent LUT cleanup still
leaves a small number of generic `$and`/`$or` cells and currently triggers a
nextpnr packing crash; that cleanup remains the active blocker before timing
analysis.

A bounded ABC pass on the boolean cone reduced it to 2,281 `LUT2`, 587
`LUT3`, 559 `LUT4`, 914 `LUT5`, and 252 `LUT6` cells. The remaining 593
inverters were isolated as the only generic boolean class. Direct JSON
replacement with native `INV` cells still crashes nextpnr, indicating that
these generated cells also need the exact per-cell provenance and port
metadata emitted by Yosys's `lut_map` pass. This remains a packaging and
legalization task; timing and hardware are unverified.

The first single-invocation source-level flow (native arithmetic/LUT mapping
before JSON export) exposed an additional issue with the global memory
annotation: small asynchronous scratch memories such as `lm_input_q16_16`
are forced to block RAM and fail Yosys memory legalization (`no valid mapping
found`). Therefore the production flow must apply block-RAM intent selectively
to the large model banks and leave scratch/control memories available for
FF/LUTRAM mapping.

The residual-cell experiment converted the remaining 2,391 muxes, 819 ORs,
13 ANDs, 14 NOTs, and 17 flip-flops into native LUT/FDRE forms, leaving only
one constant equality to encode. The resulting JSON is structurally native,
but nextpnr still crashes during packing; the generated `CARRY4`/`FDRE`
instances do not yet have the exact cell metadata emitted by Yosys's own
mapping passes. This narrows the next fix to native-cell ABI generation rather
than model memory, arithmetic width, or board capacity.

With the width-aware policy, Yosys correctly maps scratch memories and 32-bit
scale tables to LUTRAM. It still rejects the 8-bit, 16K-entry token-code
banks when forced to BRAM, even after simplifying the BRAM variant to a
registered-read process. The `memory_dff` diagnostic remains unchanged: the
generated read enable is not recognized as BRAM transparency logic. This
isolates the remaining memory work to a source-level synchronous bank
template; no datapath result or hardware claim follows.
