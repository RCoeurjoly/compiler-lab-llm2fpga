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
