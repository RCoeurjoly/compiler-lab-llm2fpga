# RC prefill-8 native-SV runtime diagnostic

The current backend frontier was narrowed with two independent checks.

## Preparation-pass A/B

Running the exact prefill flat-SCF input through the pinned MLIR plugin with
and without `llm2fpga-lower-negf-for-calyx` produced byte-identical prepared
MLIR:

```text
11311a7467d737f0f433cabffa8d3dd757f22034b0f92bd325f4d7af650ae9cb
```

The input contains no residual `arith.negf` after the preceding exact-math
legalization. The negf successor is therefore ruled out as the cause of the
current prefill runtime frontier.

## Native-Calyx reproducibility

The `sf28…` and `vvlf…` native-SV outputs consume the same Futil payload:

```text
ad341b31e06ddc57ededf8336c511713c7a450ca21cc7324ab3c054e37602115
```

but their generated `main.sv` hashes differ:

```text
sf28…  a14ec83530d724b3f75489127a6a5dc647d659fc66a64624bc2bfa1a692451b6
vvlf… 9c5605c45624cf385949cccfc4b73a9614d7d072c9b4a6e6eefc2f8b4676e5e1
```

The first difference is a wall-clock timestamp in the Morty header, followed
by a different HardFloat module closure/order (for example, one output emits
`recFNToFN` at that position while the other emits `isSigNaNRecFN`). Thus the
native Calyx wrapper is not byte-reproducible even for identical Futil input.
The two outputs also have different simulation behavior: the older cached
variant reaches `done` but mismatches the pre-repair reference, while the
newer repaired variant exceeds the 1,800-second simulation bound.

This is evidence for a backend reproducibility/convergence issue, not a
negf-lowering issue. Before further semantic debugging, the native-SV stage
must be made deterministic (at minimum, timestamp-free and with a stable
HardFloat module closure/order), then the exact prefill equivalence gate must
be rerun.
