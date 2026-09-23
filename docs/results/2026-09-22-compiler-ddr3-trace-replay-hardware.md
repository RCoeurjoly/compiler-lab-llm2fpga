# Compiler DDR3 exact trace replay on YPCB

The temporary replay diagnostic passed its hardware localization gate on
2026-09-22. The routed compiler-derived image was programmed into SRAM (the
persistent BPI flash was not modified), then the established deferred-
authorization PCIe lifecycle was used.

- Endpoint: `0000:42:00.0`, `10ee:0480`, subsystem `10ee:abcd`.
- BAR0: `0x74000000`.
- Production DDR3 calibration/BIST: status `0x61`, loader `0x3`, BIST state
  `0x17` (required done state).
- Complete image load/readback: `4,136,720` bytes; readback hash exactly
  matched `e44d9bac0ddcf267cb2b41eb6f0aee623bacfb28809d9dffb7edc0319c43e593`.
- Exact trace replay: all `13,116,912` configured, pushed, accepted,
  responded, and checked records matched; errors `0`, terminal state `2`,
  flags `5`, no mismatch index.

The bitstream hash was
`effd210f87f1ad2d7c490cfc2105aef21be2406fa0a41f859e466d11438b8156`.
This proves the PCIe-to-UberDDR3 path for the authenticated compiler-derived
request sequence. It does not yet prove the unchanged full compiler
accelerator, first-token inference, persistent BPI programming, or complete
device timing signoff.
