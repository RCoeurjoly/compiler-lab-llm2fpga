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
`artifacts/diagnostics/2026-09-23-nextpnr-flat-wire-reserve.json`.
