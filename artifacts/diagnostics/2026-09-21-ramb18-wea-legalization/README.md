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
