# XC7 RAMB18 write-enable legalization checkpoint

This checkpoint follows the pinned compiler/PCIe/UberDDR3 composition at the
fixed YPCB profile (two DDR lanes, 333/83.33 MHz, 30 MHz target, seed 15).

The first nextpnr run stopped in `connect_port` while packing the compiler
constant memory `gen_compiler_command_adapter.compiler_command_adapter.core.compiler_core.c_fc_input_codes_i8.mem.0.0`.
The cell was a `RAMB18E1` with a narrow `WRITE_WIDTH_A` but all four `WEA`
lanes serialized. XC7 nextpnr expands the used lanes itself, so the unused
lanes collided with the expansion (`WEA2` was the first collision).

The new bounded JSON legalization removes only unused `RAMB18E1 WEA` entries,
derived from `WRITE_WIDTH_A`. It does not change nets, initialization,
addresses, data, or any compiler/transport RTL. The rerun passes BRAM packing
and reaches placement. It then stops because the composed platform handoff
still contains generic/unmapped shell logic; no fit, timing, FASM, bitstream,
or hardware claim follows.

Evidence:

* `legalization-receipt.json`: two narrow RAMB18E1 cells legalized.
* `nextpnr-bram-pass-placement-failure.log`: BRAM packing passes; placement
  stops on an unmapped `$logic_and`/`$lut` path in the composed handoff.
* `nextpnr-generic-shell-placement-failure.log`: bounded attempt to map shell
  generic logic; placement still stops before fit/timing qualification.

The reusable transform is
`scripts/pipeline/legalize_xc7_primitive_json.py`.

The additional `nextpnr-ram64d-placement-terminated.log` records the next
mapped-shell experiment. The 192 temporary `RAMD64E` cells were converted to
`RAM64X1D`, the dual-port LUTRAM form handled by this pinned XC7 packer.
Packing completed and reported 290,186 LUTs, 209,350 FFs, 13 RAMB18E1, and 46
RAMB36E1, with PCIe, two BSCAN endpoints, and the fixed 30 MHz target still
present. The process then terminated during the main analytical placer before
placement/routing, FASM, or a bitstream existed. This is diagnostic evidence,
not an implementation or hardware result.

A second bounded run with `--no-tmdriv` and a ten-minute timeout reproduced the
same termination point (`Running main analytical placer`) byte-for-byte in the
captured log. It produced no routed JSON or FASM either; this rules out timing
driven placement as the sole cause of the observed stop.

The alternative `--placer sa` was also bounded and stopped after 180 seconds:
it had placed only 4,000 of 499,605 cells (about 133 cells/s) during initial
placement. It is therefore not a viable fast-iteration workaround for this
netlist; no output bitstream was produced.

Setting `OMP_NUM_THREADS=1` for the default HeAP placer reproduces the same
placement log and endpoint within the bounded run. The log hash is identical
to the timing-driven and `--no-tmdriv` runs, so OpenMP parallelism is not the
observed cause.

The locally rebuilt nextpnr-xilinx (including the available HeAP fixed-child
patch) was then run with the same inputs. It produced the identical log hash
and stopped at the same analytical-placer boundary, so that patch does not
resolve this mapped-shell failure either.

The fast-path was then corrected to map both sides of the boundary
independently. Yosys target-mapped the platform shell in 30.31 seconds, and
the compiler boundary was separately legalized: the compiler arbiter and
command adapter were ABC-mapped, compiler LUT/FF cells were converted to XC7
primitives, BRAM wrappers were converted with `brams_xc6v_map.v`, and the 192
LUTRAM banks were converted to the pinned nextpnr-compatible `RAM64X1D`
form. The port-signature checker was also corrected to compare direction and
width rather than module-local Yosys bit IDs.

The resulting composed netlist contains 240,365 slice LUTs, 51,920 slice FFs,
52 RAMB36E1, 14 RAMB18E1, PCIe, two BSCAN endpoints, and the unchanged
two-lane 333/83.33 MHz DDR3 shell. nextpnr packing completes and HeAP
placement starts on 264,636 cells. HeAP completes after 272.8 seconds and the
simulated-annealing refinement reaches iteration 5, but the bounded run ended
before routing and emitted no routed JSON, FASM, bitstream, timing report, or
hardware result. The diagnostic netlist SHA-256 is
`ec0f63bbe05bbac176537c11b5c702f37392fe35f2422186ba5db72774e1df49`; the
captured nextpnr log SHA-256 is
`f6a9bdc559c7135130c0e8b3ec660c323d5b8ab521398cb9c06f9a37f04f8a68`.

The temporary bounded-HeAP diagnostic was rebuilt from the local nextpnr-xilinx
source after changing only the zero-temperature refinement stop condition. It
was run with the same JSON, XDC, chipdb, seed 15, and 30 MHz target. Packing
completed and HeAP placed all 264,636 cells in 273.27 seconds; the first
post-placement timing report measured `rowstream_clk` at 19.20 MHz (FAIL at
30 MHz), while `pcie_user_clk` measured 50.34 MHz (PASS). The run then aborted
in post-placement legalization with `port.net == nullptr` in
`common/design_utils.cc:93`. No routed JSON, FASM, bitstream, or hardware
artifact was emitted. This temporary tool is diagnostic only and does not
alter the pinned production nextpnr package. The log is
`/tmp/t4-sa-stop-nextpnr.log` with SHA-256
`84ffeeb5dc0f2abd46508713561bbbabdc024f8856f579bd4cfca69fe9b4ec9d`.

Further diagnostic-only netlist representation experiments isolated the next
packing/routing boundaries. Restoring a two-element RAMB18 `WEA` vector (the
active lane plus a constant-disabled lane) allowed the run through global-clock
routing; it then stopped on an unused SDP RAMB36 write-side vector at
`WEA8`. Removing that vector for the two `WRITE_WIDTH_A=0` SDP cells allowed
the run to proceed farther, but it stopped on `DIADI32` of a RAMB36 cell. The
last error is consistent with the compiler-side physical memory mapping
emitting a 64-element RAMB36 data vector where the XC7 RAMB36 logical port
mapping only has indices 0--31; trimming that vector would risk changing the
memory contents and is not accepted as a production fix.

The three diagnostic netlist hashes are, respectively,
`36ce876d04f06f95644a295338c07554205fb5bba00262d9a320673a96d956f1`,
`698c8664ff4bc8b25b86f6075233301ccb01204deabc46d0f1a2a6dddaf12406`, and
`fa689fcaf98af83752d78f0e3678ae166a304d3f6e88e64e24efe93704bcff89`; their
nextpnr log hashes are
`c17f5f6327b3130ef04f33bb71bc99b52b021181c0c370d30cbfc570b4002747`,
`fbd67fd679cd07c88cd8cac688893122697019b21fdb41ca1b2e0d736d850a79`, and
`4b17aba468e7b2a6f39da80737797d348e2dbb60ae264fdfb934e612916aeb2e`.
These runs remain diagnostic only: no routed JSON, FASM, bitstream, or board
inference was produced.

The reusable legalizer was corrected accordingly (working tree revision only):
RAMB18 narrow writes retain an active lane plus a constant-disabled logical
lane, and RAMB36 SDP cells with `WRITE_WIDTH_A=0` drop the unused `WEA` port.
Running it on the composed pre-map netlist reports 3 RAMB18 and 8 RAMB36
changes. The wide RAMB36 data-port mismatch remains intentionally unresolved;
it requires a semantics-preserving bank split in the compiler physical-memory
mapping, not truncation.

The legalizer was then aligned with the installed XC7 primitive declarations
for input-side lanes: RAMB18 data/parity ports are 16/2 bits and RAMB36
data/parity ports are 32/4 bits. Output buses remain untouched until a
semantics-preserving bank split is implemented. With the input-side ABI
normalization, the temporary run again completed packing,
placement, timing analysis, post-placement legalization, and global-clock
routing. It reported the same failing `rowstream_clk` path (below 30 MHz),
then stopped at router setup on an `A6` port of an LUT5-side compiler arbiter
cell. No LUT rewrite was applied. The normalized diagnostic netlist SHA-256 is
`c9fbaf4b2a2d8d21c8c61e6bed50590bc2ebabba133019c43519989462e7b68c` and the
log SHA-256 is
`e1a748e2d95ed222ad17d276746c3f92484fa62d14ba82b2bb6bd7da4191bb9e`.

A nextpnr-only diagnostic guard that omitted synthetic A6 connections when the
selected BEL had no A6 wire did not produce a usable handoff: the run instead
returned to the existing post-placement `port.net == nullptr` assertion. The
guard was removed from the external nextpnr tree; no production nextpnr source
was changed.

Combining that guard with idempotent same-net handling also did not advance the
handoff: the run stopped in the same post-placement legalization assertion,
now at `common/design_utils.cc:95`, before routing. The combined diagnostic
log SHA-256 is
`4159df1cf8603eeea519bb63c5f9fb22bae989b9fcac36e6a83d130d057dc7ee`.

The reusable legalizer now has a focused regression suite in
`tests/test_xc7_primitive_json_legalizer.py`. The pinned Python environment
reports 3/3 passing cases: narrow RAMB18 write-enable/physical-width
normalization, removal of an unused SDP RAMB36 write-enable port, and a
fail-closed check that consumed output lanes are never silently truncated.
This validates the JSON transformation boundary only; it does not waive the
remaining RAMB36 bank-splitting, routing, timing, or hardware gates.

An instrumented diagnostic nextpnr rerun localized the post-placement failure:
the compiler arbiter LUTX cell ending in `$abc$726896$auto$blifparse.cc:557:
parse_blif$728733` receives `A6` first on `$PACKER_GND_NET`, then the Xilinx
fixup attempts to reconnect the same port to `$PACKER_VCC_NET`. The abort is
therefore a duplicate constant connection in nextpnr's LUT legalisation, not
a DDR3 transaction or PCIe ingress failure. The instrumentation was removed
after capture; this run remains diagnostic and produced no bitstream.

Applying the same disconnect operation temporarily to the diagnostic nextpnr
build removed the duplicate-port assertion and advanced the run through global
clock routing. It then failed at router setup on a different compiler-arbiter
LUTX `A6` sink (`...parse_blif$728850`). The temporary source change was
reverted; the diagnostic log SHA-256 is
`1c90839f4deee08be8a73bfa6920c73c517f54ff484314548b4274187a87395b`.

The temporary constant-only cleanup of invalid `A6` on B5LUT sites removed
that router failure as well. The run then reached a RAMB address endpoint and
stopped on `ADDRARDADDR16` at
`gen_compiler_command_adapter.compiler_command_adapter.core.attention_context_heads_q16_16.mem.0.0`.
This is the next physical primitive/port legalization boundary; no routing,
bitstream, or hardware claim follows from the diagnostic. The cleanup is
captured as the dry-run-applicable patch
`patches/nextpnr-xilinx/0024-drop-constant-a6-on-lut5.patch`.

The v4 compiler JSON legalizer additionally normalizes the pinned 72-bit
RAMB36 map's 17-lane address vectors: it removes the proven-unused zero lane
while retaining the map's constant-one extension at the physical MSB. Five
focused legalizer tests pass, including a fail-closed unexpected-address case.
The resulting temporary nextpnr run clears the previous RAMB `ADDRARDADDR16`
failure and has entered the main router loop; its outcome is still pending.
The attached rerun has now reported router iteration 1 (`5,901,155` wires,
`282,952` overused wires, total overuse `295,833`); this is route progress, not
yet a routed-design or timing result.

The attached v4 route subsequently converged and emitted FASM, but nextpnr
returned nonzero at post-routing timing: `rowstream_clk` reached only 25.20
MHz against the 30 MHz constraint. PCIe and all auxiliary clocks passed. The
critical path is the compiler-generated `c_fc_requant_product` absolute-value,
bias, shift, and rounded-negation chain; no RTL or arithmetic change has been
made. Diagnostic hashes are:

* mapped JSON: `24920004ed4d3610c5b5d129115ac07d05d128e9228ca5f413fc609dc8c6294a`
* FASM: `554d8adc91d75d4e0ecfc9833064e51b152ac747cc89df08b44ed870bc3ebbf6`
* nextpnr log: `e230b6bb2c834c097359d2058010d1e1bb2a8fb781258e650e4744597a20c8c7`

This is a routed diagnostic artifact, not a timing-qualified bitstream or
hardware result.

## Evidence-backed requantization narrowing

The authenticated reachable-domain certificate bounds every projection
accumulator times Q8.24 weight-scale product below `2**52`. The compiler
lowering therefore now accepts `narrow_products=True` for production
projection requantization. It uses a signed 53-bit internal multiply,
absolute-value, bias, shift, and rounding chain, then sign-extends the result
back to the existing 64-bit post-QDQ memory ABI. Diagnostic/non-production
lowerings remain byte-identical 64-bit implementations.

Checks completed:

* `tests.test_tinystories_1m_bram_production`: 20/20 passing, including
  directed/random signed-64-versus-53-bit rounding equivalence.
* Direct Calyx lowering of the production one-step model: succeeded; Futil
  SHA-256 `4ba9adcdc657dc3c5230dc6d1d12668984a2dfe876d55c084ff08a794072b625`.
* Generated SystemVerilog Verilator lint: passed.
* Yosys SystemVerilog import, hierarchy, process, optimization, and stats:
  passed; no parser or width errors.

This optimization has not yet been mapped, routed, timing-qualified, or
programmed on YPCB. The next gate is to run the unchanged XC7/PCIe/UberDDR3
mapping and fixed-seed route flow on this regenerated compiler output and
measure whether `rowstream_clk` clears 30 MHz. No hardware or inference claim
follows from the frontend checks.
