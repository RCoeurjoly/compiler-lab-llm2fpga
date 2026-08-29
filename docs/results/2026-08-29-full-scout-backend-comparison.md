# TinyStories-1M full scout backend comparison

The full SCF artifact can be lowered to Calyx after the explicitly
approximate polynomial-`exp` resource-scout pass.  Exporting Calyx MLIR to
Futil and invoking the pinned Calyx Verilog backend with verification disabled
produces a 1,023,692-byte baseline Verilog file.  Yosys reports 11,548 cells,
21,270 wires, and 362,486 wire bits.

The same Futil with `cell-share` disabled produces 1,356,771 bytes, 12,486
cells, 32,774 wires, and 800,666 wire bits.  Thus the candidate increases
cells by 938 and wire bits by 438,180 and is rejected for the full artifact.

This is structural resource-scout evidence only: polynomial `exp` is not the
authenticated TinyStories fixed-point implementation, and no functional,
timing, FPGA, or hardware-inference claim follows from these files.
