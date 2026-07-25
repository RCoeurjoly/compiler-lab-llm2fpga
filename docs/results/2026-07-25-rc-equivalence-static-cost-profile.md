# RC equivalence static cost profile

This profile was produced by the Nix derivation `tinystories-w8a8-rc-sv-static-cost-profile` from the existing V=6 W8A8 Calyx native-SV artifact and its cached Verilator output.

- SV: 9,955,404 bytes and 293,285 lines across 66 modules.
- HardFloat/float-related textual matches: 23,278.
- Memory-port references: 6,164.
- Wide assignments: 85; largest assignment: 696,736 characters.
- Verilator C++ units: 435, totaling 192,992,515 bytes.
- Largest generated C++ unit: 1,253,550 bytes.

This is structural cost attribution, not yet a fresh compile-time or simulator-throughput measurement. The immediate hypothesis is that the monolithic control/HardFloat lowering creates a large number of expensive C++ evaluation units; the next experiment must measure translation, C++ compilation, and runtime separately.
