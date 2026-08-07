# RC Q4.12 `roundeven` mismatch investigation

## Status

The strict context-0 equivalence gate is not yet green. Compilation of the
diagnostic closure succeeds, but the host supervisor terminates the long
Verilator execution before the model reaches its normal completion near
cycle 514,919. No oracle criterion was weakened.

## Earliest divergence

The frozen PyTorch oracle for context 0 is:

```text
18,-93,-34,7,20,1; token=4
```

The first differing scratch boundary is port 94. Port 93 contains the finite
masked value `ff7fffff` (`-FLT_MAX`). In the later Q4.12 requantization path,
division by the exact scale `2^-12` (`2.44140625e-4`) produces `-inf`
(`ff800000`). The existing round-to-nearest-even expansion then performs:

```text
fptosi(-inf) = 0x80000000
0x80000000 - 1 = 0x7fffffff   (32-bit wrap)
sitofp(0x7fffffff) = +2^31
```

The following int8 conversion therefore observes `+2^31` and emits `0x7f`
instead of the expected masked `0x80`. This is an arithmetic exceptional-value
bug, not a Handshake-dialect issue.

## Implemented lowering change

`llm2fpga-lower-roundeven-for-calyx` now adds a narrowly scoped guard only for
roundeven inputs whose defining division uses the RC exact Q4.12 scale. The
guard selects the original input when it is below `-FLT_MAX`, covering the
observed `-inf` result while leaving finite values on the normal roundeven
path. The checked-in reproducer is
`reproducers/calyx-math-roundeven/nonfinite.mlir`.

The pass and real-plugin regression tests pass. A complete strict context-0
run using the regenerated closure remains required before this goal can be
marked complete.

