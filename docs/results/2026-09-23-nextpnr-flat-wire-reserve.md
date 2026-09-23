# nextpnr router2 wire-storage diagnostic

Massif profiling of the full compiler-generated TinyStories-1M route showed
that `Router2::setup_wires()` spent about 2.4 GB in repeated `flat_wires`
vector reallocation. The repository already reserved the separate wire-index
hash, but not this vector. Patch
`patches/nextpnr-xilinx/0038-router2-reserve-flat-wire-storage.patch` adds
that reservation without changing routing semantics.

The patched nextpnr-xilinx binary compiled successfully in the pinned Nix
development environment. A bounded seed-15 route of the unchanged full
compiler netlist reached the 122,303-cell analytical-placement startup, but
did not produce a timing report or FASM during the bounded observation. This
is therefore a tool-memory diagnostic, not timing closure or a bitstream.

The machine-readable evidence is in
The patched tool was then checked against the known-good replay netlist. It
emitted FASM and post-route timing passed at 97.54 MHz rowstream and 76.51 MHz
PCIe. The unchanged full accelerator was rerun for 1200 seconds: it reached
router2 iteration 1 but timed out with no FASM and retained the earlier
37.09/40.88 MHz placement timing and 19.42 ns PCIe-to-rowstream path. Thus the
allocation fix is baseline-safe but does not solve full-design routing; the
next change must address the full compiler/DDR netlist structure or its
placement, not repeat this allocator patch.

The machine-readable evidence is in
`artifacts/diagnostics/2026-09-23-nextpnr-flat-wire-reserve.json`.
