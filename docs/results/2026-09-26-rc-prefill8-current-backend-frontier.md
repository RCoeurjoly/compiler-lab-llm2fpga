# Current RC prefill-8 backend frontier

The prefill artifact-pairing question is resolved at the Nix derivation level.
The `sf28…` native-SV output is produced by the Calyx derivation whose input is
the `skgj…` flat-SCF derivation; the flat-SCF payload hash is
`5fd9efe083f44b29d961a50f8d8487e094a88c5d0c15e0465b133a47cb9829e9`. The
reference package is the stable `yr0…` output (reference hash
`3188f16fa6f89b1ad772c205032cf632389aed4994f210ad4e64ca513ddc5191`).

Two bounded observations follow:

1. The cached `assf…` native-SV variant completed in 545,149 cycles, but the
   canonical harness returned `mismatch` for all five outputs. Its report is
   `/tmp/rc-prefill8-authenticated/report.json` (SHA-256
   `a335bdd38dafcd91d97c58451a73890f7a481fdcd33249ccbda254b253065a47`).
   Its manifest has no `divsqrt-handshake-receipt.json`; the numerical errors
   reproduce the previously documented pre-repair prefill failure.

2. The current `sf28…` variant includes the div/sqrt handshake receipt and was
   compiled successfully with Verilator `-j1 -O0`. Its simulation did not
   produce `done` or output files within the 900-second bound, and an extended
   already-built-binary run was bounded at 1,800 seconds. This is a runtime
   frontier, not a semantic mismatch result.

The historical repaired three-phase receipt (`16b1189`) reports a prefill
simulation of 580.66 seconds and bit-exact outputs, but its native-SV closure
(`xx13…`, SHA-256 `1657b663…`) has been garbage-collected. Therefore that
historical claim cannot be replayed from the current store without rebuilding
the historical closure.

## Decision boundary

Current prefill equivalence is not re-qualified on the present branch. The
next experiment must either reproduce the historical repaired closure from its
recorded commit or isolate the post-closure backend/runtime regression. No RC
composition, synthesis, PCIe, DDR3, bitstream, or board claim is promoted from
this frontier.
