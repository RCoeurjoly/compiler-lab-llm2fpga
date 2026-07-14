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
nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-il --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-main1-il -L
```

`lower-scf-to-calyx` completed. The following native-SV generation failed
before RTLIL or Yosys because CIRCT-exported Futil imports float primitive files
that are absent from the pinned Calyx 0.7.1 library. The detailed diagnostic is
recorded in `.superpowers/sdd/task-4-report.md`; raw logs are intentionally not
copied into this documentation or the compact artifact bundle.

## Resources

No mapped resource estimate exists (`resources: null`). The monitor recorded a
frontend peak of `peak_vmrss_kb: 567136` for `nix` and an empty
`last_stage_line: ""`. Consequently this route has no LUT, FF, BRAM, DSP,
nextpnr, or board figures.

The monitor inputs briefly overlapped during execution; this is an execution
caveat only and does not change the recorded frontier.

## Interpretation

This is a compiler compatibility frontier, not an out-of-context resource
estimate. It is not a DDR3 controller, board implementation, nextpnr result,
or numerical-equivalence result.

## Decision

The native-SV frontier ends this plan. Any toolchain-compatibility repair or
partitioned attempt requires a separately approved design. No W8A8-versus-F32
factor is claimed because comparable mapped results do not exist for both
reports.
