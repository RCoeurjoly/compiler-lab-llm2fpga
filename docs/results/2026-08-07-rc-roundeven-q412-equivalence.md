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

The strict diagnostic closure used the exact script output hashes:

```text
input main.sv   sha256=3ef261f87a4488b2347561c49d03462b23519ea5900d2c5b3f5dcc1f942266e6
output main.sv  sha256=1d87bfed9a5ef283b53e74ab48de1b6fffec8d23d5827799cbb15969d91abc67
```

The frozen oracle and testbench were unchanged; the result was the
`CASE_PASS`/`SHARD_PASS` shown above. A regenerated closure from the current
target is still required to replace this retained diagnostic artifact.

## Flat-emission unblock

The nested Calyx emitter was not the only expensive phase: the equivalence
only target also invokes a second synthesized resource-report pass unless it
is explicitly disabled. Commit `a5673b6` adds `CALYX_SKIP_RESOURCE_REPORT=1`
for equivalence-only builds and selects flat (`CALYX_EMIT_NESTED=0`) emission.

The resulting current-pipeline closure was generated successfully:

```text
SV: /nix/store/yk48hnxvmb9l3b5pv90cf2fzqsk52mpy-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv-no-synthesis/sv/main.sv
SV bytes: 18,912,173
Verilator generated C++: 134,185,438 bytes in 199.229 s
Verilator compile: 496.348 s
```

The strict run on this fresh flat closure completed the 600,000-cycle bound,
but did not produce an output for any of the four diagnostic inputs:

```text
RESULT ascending   -1 -1 -1 -1 -1 -1
RESULT descending  -1 -1 -1 -1 -1 -1
RESULT zeros       -1 -1 -1 -1 -1 -1
RESULT alternating -1 -1 -1 -1 -1 -1
```

At the bound the model had made and completed memory requests, but remained
`done=0` with `output_writes=0`. The flat closure therefore exposes a
liveness/handshake or scheduling incompatibility with the strict testbench;
it is not an equivalence pass and increasing the timeout alone is not a
justified fix. The next debug step is a flat-versus-nested signal comparison
at the first state where output production diverges.
