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
