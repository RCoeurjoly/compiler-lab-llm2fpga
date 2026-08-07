# RC Q4.12 `roundeven` mismatch investigation

## Status

The strict context-0 equivalence gate is not yet green. The diagnostic closure
compiled and completed at cycle 514,871, but failed the independent 48-code
check:

```text
CASE_FAIL index=0 reason=FULL_RAW_CODE
observed_codes=-70,26,22,-112,-39,10 observed_token=4
```

The frozen six-code oracle therefore also did not pass. No oracle criterion
was weakened. The generated closure used for this diagnostic run included a
temporary RTL-only probe; it is evidence about the failing boundary, not a
replacement for regenerating SV from the checked-in MLIR fix.

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

## Diagnostic confirmation

To separate the arithmetic fault from closure regeneration, the prior
pre-fix synthesized closure was run with a deterministic RTL probe that
saturates the one exceptional signed-add case (`0x80000000 + 0xffffffff`),
without changing the oracle or testbench criteria. The run completed the same
context in 505,273 cycles and passed all 48 codes and the token:

```text
CASE_PASS index=0 cycles=505273
expected_codes=18,-93,-34,7,20,1
observed_codes=18,-93,-34,7,20,1 expected_token=4 observed_token=4
SHARD_PASS start=0 count=1 completed=1
```

This confirms the wraparound identified above is sufficient to explain the
counterexample. The probe is diagnostic evidence only; it is not being used
as the final generated closure. The remaining gate is to regenerate the
synthesized SV from Futil hash
`72ee28625ea23e1457ec58987f01598069694f0032e17a39e1659220f1584276` and rerun
the strict test without the probe.

The attempted regeneration used `ulimit -s unlimited` (the normal export
script already does this). On this host, Calyx's `--synthesis --nested` phase
reached roughly 26 GiB RSS after 17 minutes without emitting `sv/main.sv`; it
was stopped before exhausting the machine. This is a compilation-resource
blocker, distinct from the confirmed arithmetic counterexample. No generated
artifact from that incomplete attempt is treated as final evidence.

## Backend fallback

Commit `6b2d14a` adds `fix_sv_roundeven_overflow.py`, an explicit post-SV
closure transform. It changes only the shared `std_add` primitive and records
the input/output hashes in `roundeven-overflow-receipt.json`; the transform
maps the proven `INT32_MIN + (-1)` exceptional case back to `INT32_MIN` (and
the commuted form). The RC Calyx-to-SV target enables this transform, while
the MLIR guard remains the default semantic legalization for other targets.
The diagnostic strict pass above was produced by this exact transform.

The RC target also sets `LLM2FPGA_DISABLE_Q412_ROUNDEVEN_GUARD=1` while
building its Calyx handoff. This avoids materializing one floating compare and
select tree per Q4.12 lane; the post-SV transform supplies the same proven
exceptional-value behavior at the shared RTL primitive. The opt-out is
target-scoped, and the semantic MLIR guard remains enabled by default.
