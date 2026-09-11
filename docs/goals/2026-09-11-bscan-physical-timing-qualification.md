# Physical BSCAN timing qualification

Status: active

## Objective

Isolate and fix the YPCB physical `BSCANE2` capture/shift response alignment
without changing the TinyStories model, accelerator, 64-bit JTAG ABI, or
validated 30 MHz implementation constraints. Use a separately validated
CSR-only sentinel with recognizable response patterns and counters for
CAPTURE, SHIFT, and UPDATE. Exercise it through the canonical HS3/MPSSE
transport and record raw TDO bits while sweeping only scan-edge mode, TCK rate,
TDO extraction bit, and capture length. Reproduce the measured TAP vector in
`BSCAN_SIM`, identify the first physical-vs-simulation divergence, and apply
one minimal evidence-backed RTL correction.

## Acceptance gates

1. The existing BSCAN sentinel still passes through the canonical transport.
2. The CSR-only sentinel produces a stable, explainable raw-bit offset/pattern.
3. Simulation reproduces the measured raw sequence.
4. One corrected CSR image passes reset, status, prompt write/readback, and
   START on hardware twice without reprogramming between commands.
5. Only after those gates pass, return to the TinyStories image and run the
   two-token, then 16-token, acceptance protocol.

No host-side bit shifting or ABI change is an acceptable substitute for the
RTL/physical timing correction.

## Initial control result (2026-09-11)

The existing sentinel was reprogrammed through the HS3 and read with the
canonical MPSSE transport at 1024 bits. It passed (`magic_ok=true`, magic
`0x54364a44`, version `1`), confirming that the cable, programmer, USER1
selection, and host TDO extraction path are operational before CSR-specific
experiments.

The physical sweep also passed at capture lengths 64, 65, 66, and 1024 bits.
TDO extraction bit 7 decoded correctly while bit 0 did not. With bit 7, the
sentinel remained valid at 100 kHz, 1 MHz, 6 MHz, and 12 MHz MPSSE rates; its
counter advanced on every read. Thus generic BSCAN capture/shift timing and
host sampling are stable. The `0x07`/`0x0f` TinyStories result is localized to
the CSR response path or its interaction with the system clock, not the cable,
TDO bit, scan length, or global JTAG rate.

The first CSR-only top elaborates, but its inert core-side constants are
constant-folded by Yosys and leave an unplaceable asynchronous FF form in
nextpnr. This is a diagnostic-top synthesis issue, not evidence about
physical BSCAN behavior; the fixture needs observable, non-constant inputs.

An explicit temporary map converts the remaining async FFs to `FDCE`/`FDRE`,
but nextpnr then rejects a generated FF with no resolvable `C` direction. The
diagnostic image is therefore not programmed; the production toolchain's exact
FF mapping sequence must be reused before hardware CSR conclusions are drawn.

Using the production `synth_xilinx` flow, the CSR-only image routed and was
programmed successfully (bitstream SHA-256
`c990a0d56bb792469c96d4e8c9d5283608a946157946a0fa7de0ab834e55b6b5`). The
canonical CSR harness then failed on the first command: reset returned
`0x00000000000000ab` instead of zero. The sentinel's token value is `0xab`, so
the command opcode is being misdecoded as a token-read operation before any
TinyStories logic exists. This is the first hardware-vs-simulation divergence
at the CSR command boundary.

The minimal command correction was built and programmed (bitstream SHA-256
`5e9a3ce4bb37e270ab93a4bab9f73f20f08e68963b0da5c918df49fcb0cc17d9`). Hardware
reset now returns zero, proving the opcode MSB is restored. The following
status command still returns zero instead of `0x2800000000000000`; command
integrity is fixed, while the remaining mismatch is response/event CDC timing.
