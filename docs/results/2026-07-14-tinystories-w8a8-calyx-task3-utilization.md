# TinyStories W8A8 Calyx Task 3 utilization frontier

## Method

The attempted route was `PyTorch PT2E W8A8 -> Torch-MLIR -> TOSA -> Linalg ->
SCF -> Calyx -> native SV -> Task 3 Xilinx synthesis`, using `main_1` as the
out-of-context compute/control top. The nested Task 3 toolchain was Yosys
`unstable-4716f441` at
`4716f4410f1508cad384d2f8542ada9f61bb7339` and the `yosys-slang` input at
`d82b0b163a725fc1a401fbb6b465cd862517ec1f`.

The intended device is the XC7K480T: 74,650 slices, 298,600 CLB LUTs, 597,200
CLB FFs, 1,920 DSPs, 955 BRAM36 blocks, and 34,380 KiB of BRAM. The external
memory boundary remains 2,133 logical memories, represented at `main_1` by
12,802 ports and 115,933 port bits; its interface evidence is
`expected-unverified` and requires the `done` output.

## Result

[`result.json`](../../artifacts/tinystories-w8a8-calyx-task3-utilization/result.json)
records `status: "frontier"`, `completed_stages: []`, terminal stage
`"native-sv-generation"`, and `exit_status: 1`. Its exact command was:

```text
nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-native-sv -L
```

`completed_stages: []` means that no Task 3 mapping stage completed. Before
the frontier, the full W8A8 Linalg, SCF, flat-SCF, and lower-SCF-to-Calyx
stages completed and produced a 18,613,223-byte `model.futil`. The failed
derivation was
`/nix/store/2zmb3z0602x6s109j8mmcw9l7fg1j0vc-tinystories-w8a8-calyx-native-sv.drv`;
its inspectable failed output is
`/nix/store/2mrlpwn1ibvxsfxhqp6j1jfv66vmrvjk-tinystories-w8a8-calyx-native-sv`.

Native Calyx began the Verilog export and was killed by the operating system
during SV emission. The named output has no `sv/main.sv`, so the full model did
not reach SystemVerilog, RTLIL, or Yosys. Its native-Calyx log records
data-path inference not converging after five iterations, `cell-share:
103999ms`, and `compile-invoke: 121417ms`. Live telemetry immediately before
the kill reported about 28.6 GiB RSS, about 450 MiB available host RAM, and no
usable swap. The detailed command and failure record is in
`.superpowers/sdd/calyx-float-task-4-report.md`; raw logs are intentionally not
copied into this documentation or the compact artifact bundle.

## Resources

No mapped resource estimate exists (`resources: null`). Consequently this
route has no LUT, FF, BRAM, DSP, nextpnr, or board figures.

## Interpretation

This is a native-Calyx memory frontier, not an out-of-context resource
estimate. It is not a DDR3 controller, board implementation, nextpnr result,
or numerical-equivalence result.

## Decision

The native-SV frontier ends this plan. Any toolchain-compatibility repair or
partitioned attempt requires a separately approved design. No W8A8-versus-F32
factor is claimed because comparable mapped results do not exist for both
reports.
