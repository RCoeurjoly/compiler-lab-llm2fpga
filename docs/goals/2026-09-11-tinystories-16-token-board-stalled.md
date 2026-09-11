# TinyStories-1M compiler candidate board inference

Status: stalled

## Objective

Turn the routed, timing-qualified TinyStories-1M registered-argmax compiler
candidate into a usable board accelerator. Preserve the authenticated model,
fixed-point arithmetic, BRAM/LUTRAM mapping, JTAG ABI, 30 MHz constraints,
seed 15, and routed implementation unchanged. Convert the verified routed FASM
to a Kintex-7 bitstream, program the YPCB without unnecessary privilege, run the
frozen prompt for autonomous 16-token generation with FPGA token feedback, and
require exact token-by-token agreement with the authenticated reference within
300 seconds on three independent cold-start SRAM reconfigurations. Record
bitstream/provenance hashes, timing/resource reports, board logs, and
first-mismatch diagnostics; do not claim success if programming, token
feedback, or any checkpoint diverges.

## Stall evidence

Bitstream conversion, programming, and the HS3/JTAG transport are proven.
The canonical hardware CSR test deterministically fails before START:
hardware returns `0x0700000000000000` instead of
`0x2800000000000000`. RTL CSR simulation passes. No inference has started.

The blocker is therefore the physical BSCAN capture/TDO timing boundary, not
the model, BRAM contents, or accelerator arithmetic.
