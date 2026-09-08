# TinyStories-1M compiler bitstream board-validation checkpoint

The patched nextpnr route produced and programmed the 30 MHz compiler-generated
BRAM image `/tmp/tinystories-fixed.bit` (SHA-256
`563aaefb2c4eedd2f0917df85db5129687eeafb47c81b461c3c50952482e8cae`).
`openFPGALoader --cable digilent_hs3` completed with `isc_done=1`, `init=1`,
and `done=1`, without privilege escalation.

The compiler top's USER1 CSR was then probed over the existing Digilent HS3
libftdi transport after TAP reset, status, and CSR-reset transactions. No
response word was observed (all-zero captures). A fixed-pattern scan diagnostic
had the same result in the preceding hardware isolation run. Therefore this
checkpoint proves configuration, but not CSR communication, model execution,
or inference.

The probe also exposed a host-side framing detail: the compiler CSR shifts its
64-bit command into the MSB-first register orientation, so a future driver
must explicitly bind command bit ordering to the RTL ABI. The existing kev-gpt
packet transport remains unchanged; no transport or RTL fix is accepted by
this checkpoint.

## Remaining gate

Resolve and verify physical USER1 selection/capture for the compiler top, then
issue prompt/start commands, observe completion and token readback, compare the
frozen TinyStories-1M reference, and repeat three cold starts with recorded
latency. Until then, board inference is unverified.
