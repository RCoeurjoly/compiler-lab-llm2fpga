# RC Verilator iteration-cost investigation

## Result

The apparent time-zero simulation hang was a testbench-control bug, not a
property of the DUT, image loading, paging normalizer, Verilator split size, or
thread count.  The reusable fixture read its runtime controls through
`$value$plusargs`, but assigned each return value only to an otherwise unused
variable.  Verilator correctly optimized those calls out.  Thus
`+case_index=0`, the watchdog, and heartbeat controls never took effect;
the default `selected_case_index=-1` started every frozen-case coroutine at
once.

The fixture now uses every plusarg result in a semantically live range or
boolean-normalization guard.  Inspection of generated C++ changed from zero
plusarg helpers to five `VL_VALUEPLUSARGS_INI` call sites.  This preserves the
documented valid command-line ABI while preventing the controls from being
dead-code eliminated.  Cache metadata is schema version 2 and includes the
fixture mode, so a run-only invocation cannot reuse a binary built for a
different fixture.

## Controlled observations

All points below retain the raw DUT, image, manifest, and frozen reference.
The simulation-side page normalizer remains conservative and four-state
checked; it is not a functional-equivalence result on the RC itself.

| Point | Result |
|---|---|
| Historical `100/50`, one Verilator thread | 18,694 generated C++ files / 136,070,102 bytes; code generation about 45 s; generated-C++ compilation exceeded a 20-minute guard during archive/link. |
| `500/250`, 1 or 8 Verilator threads | Did not reach a one-cycle watchdog before the guard **while the plusarg bug was present**.  These runs do not diagnose the split or threading setting. |
| `10,000/10,000`, 8 threads, static one-case fixture | Reached heartbeat and one-cycle timeout in about 0.01 s.  This isolated fixture selection/control as the differentiator. |
| `10,000/10,000`, 8 threads, repaired dynamic fixture | 381 generated C++ files / 197,053,017 bytes; one cycle completed in about 0.01 s, and 1,000 cycles completed in 0.30 s wall time. |
| Same repaired binary, bounded to 400,000 cycles | Completed normally in 131.85 s wall time (1,054.67 s aggregate user CPU; about 8 cores).  It reported 7,245 / 14,246 / 20,653 / 28,004 matching requests and completions at 100k / 200k / 300k / 400k cycles, respectively, with no output yet. |

The last point establishes a clean remaining frontier: after startup is fixed,
the representative core advances at roughly 3,033 cycles/s through its static
schedule, but first output was not observed within 400,000 cycles.  Equal
request/completion counts in that bounded window are evidence against an
outstanding external-memory response, not proof that memory is never a
bottleneck.

## Canonical iteration settings

The regular reusable equivalence build and first-output diagnostic now request
four Verilator front-end jobs, four generated-C++ build jobs, eight model
threads, and coarse `--output-split 10000 --output-split-cfuncs 10000`.
This avoids the pathological tiny translation-unit fan-out of the historical
`100/50` point.  The matrix keeps a coarse single-thread comparison and a
`500/250` threaded point; the much finer `100/50` point remains available only
as an explicit experiment because it generates tens of thousands of files.

The canonical reproducible build records the exact code-generation and C++
build durations in `compile-timing.json` when it reaches those stages.  A
fresh cold attempt was deliberately bounded after about 41 minutes wall time
(more than 38 minutes of single-core native Calyx emission) without reaching
Verilator.  That is a lower bound on the upstream producer, not a failed
Verilator compile and not an exact smoke result.  Do not infer a cold-build
speedup solely from the direct binary experiments above.

## What changed in the runner

- A dynamic fixture remains the default and runs all frozen cases unless
  `--case-id` selects one at runtime.
- `--static-fixture-case --case-id ID` is a diagnostic mode that compiles only
  one case, without a runtime case selector.  Its cache identity is distinct
  from the reusable fixture.
- Runtime controls are quiet by default and every valid plusarg, including
  `+stop_after_output=0` and `+trace_output_writes=0`, overrides a compiled
  default.  Code generation, C++ build, and run time are recorded separately.
- The paged/balanced normalizer is deliberately simulation-only and declines
  expressions outside its proven unsigned forms.  Its synthetic four-state
  semantic check remains required.

## Acceptance status

The repaired runner has focused unit coverage, including a test that asserts
the generated plusarg guards are semantically live.  The normalizer semantic
derivation passed previously.  No one-case raw-code smoke, four-case exact
smoke, or exhaustive `6^8 = 1,679,616` promotion gate is claimed here.  Those
contracts are unchanged and must be run before a semantics-affecting design
change is promoted.
