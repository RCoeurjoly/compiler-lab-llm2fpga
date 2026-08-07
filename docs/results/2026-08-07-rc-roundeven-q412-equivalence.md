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

The generated flat RTL explains the structural difference: it contains an
integrated `main` component plus an external-memory `main_1` invocation
wrapper. The wrapper gates its memory request/read-data/done connections on
`invoke0_go_out`; the nested emitter instead emits one integrated `main`.
The flat run's `main_1` FSM advances and completes memory transactions, but
never asserts the output memory write, consistent with a liveness failure in
this wrapper form rather than a numerical mismatch.

Bounded nested-emission experiments with `inline`, `cell-share`, and
`infer-data-path` disabled did not produce SV within five minutes. They were
stopped before memory exhaustion; none is accepted as a semantic workaround.

A focused flat-wrapper probe at the first diagnostic timeout recorded:

```text
HEARTBEAT ascending cycles=100000 state=1828 inner_state=1
  go_int=1 signal_reg=0 awaited_done=0 mem_en=0 done=0
  requests=7065 mem_completions=7065 output_writes=0 last_port=94
WRAP_DEBUG cycle=0 invoke_go=1 invoke_done=0 out_en=0 out_we=0
```

The wrapper's invoke signal remains asserted, so the failure is not caused by
the wrapper dropping `go`; the inner invocation never returns `done` after
the memory traffic completes. This narrows the repair target to the flat
invocation/static-control lowering rather than output-memory wiring.

## Top-level promotion hypothesis (falsified)

To distinguish wrapper wiring from the generated component's own control, an
experimental pass promoted the invoked `main_1` component to the Calyx
top-level and emitted a single flat RTL module. This closure also compiled
successfully (normalized SV SHA-256
`4dd89e9f485dfdd2344ba9e6bdc918f7761184c3ec9bbd2b3281b63fe6d9cdc9`), but the
strict `zeros` diagnostic reproduced the same stall:

```text
RESULT zeros -1 -1 -1 -1 -1 -1
HEARTBEAT zeros cycles=100000 state=1828 inner_state=1
  go_int=1 signal_reg=0 awaited_done=0 mem_en=0 done=0
  requests=7065 mem_completions=7065 output_writes=0 last_port=94
```

Therefore removing the `main`/`main_1` wrapper is not sufficient. The
liveness defect is intrinsic to the flat lowering/control schedule (or to a
shared generated primitive), not merely to top-level invocation wiring. The
promotion pass is not part of the active pipeline and must not be treated as
a fix.

The first direct control divergence is visible at FSM state 1828. In the
retained nested closure, the transition guard is:

```text
fsm0 == 1828 && invoke907_done_out && tdcc_go_out
```

and `invoke907_done_in` is driven by `mulf_87_reg_done`. In the fresh flat
closure, the corresponding guard is:

```text
fsm0 == 1828 && wrapper_early_reset_static_seq136_done_out && tdcc_go_out
```

but `wrapper_early_reset_static_seq136_done_in` is driven by `signal_reg_out`.
The heartbeat shows `signal_reg_out=0` indefinitely. This is the concrete
flat-lowering liveness defect to repair; it is not an oracle mismatch or a
timeout-selection problem.

### Single-wire repair rejected

As a falsification test, a temporary closure transform rewired the flat
state-1828 guard from `signal_reg_out` to `mulf_87_reg_done`, matching the
nested `invoke907_done_in` source. The repaired RTL compiled successfully, but
a fresh 100,000-cycle strict run still reported:

```text
HEARTBEAT ascending cycles=100000 state=1828 inner_state=1
  go_int=1 signal_reg=0 awaited_done=0 mem_en=0 done=0
  requests=7041 mem_completions=7041 output_writes=0
TIMEOUT ascending 100000
```

The one-wire substitution is therefore not a fix and has been removed from
the active pipeline. The evidence still identifies state 1828 as the first
observable divergence, but the correct repair must address the flat control
schedule or its generated static-control component rather than substituting
one completion signal.

Disabling Calyx's `inline` pass for flat Verilog emission also left the same
state-1828 guard (`wrapper_early_reset_static_seq136_done_out`) in the output;
the flat scheduler therefore introduces this control shape before the
individual component inlining choice. No-inlining was not accepted as a
workaround.
