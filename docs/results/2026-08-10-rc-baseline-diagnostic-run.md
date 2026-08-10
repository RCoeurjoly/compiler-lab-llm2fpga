# RC baseline diagnostic run

## Status

The agreed one-input context-0 diagnostic was started against the existing
strict Verilator fixture and the frozen oracle shard
`/tmp/rc-actual-oracle-aQg6z2/shard-0-1.hex`.

The oracle and fixture ABI were accepted. A bounded 1,000-cycle run failed
with no output writes:

```text
CASE_FAIL index=0 reason=TIMEOUT cycles=1000
expected_codes=18,-93,-34,7,20,1 expected_token=4
observed_codes=0,0,0,0,0,0 write_mask=000000
```

A 100,000-cycle run exceeded a 60-second host wall-time budget without a
completion record. A longer 600,000-cycle attempt was stopped after the host
session stopped yielding reliable process output; it is inconclusive, not an
RTL pass or a functional timeout.

## Root-cause evidence boundary

This fixture exposes final writes and cycle-bound failures, but does not emit
the requested internal semantic-checkpoint or scratch-boundary trace. The
current run therefore localizes only to “no final write by the short bound.”
The prior retained investigation remains the stronger boundary evidence: the
first differing scratch port was 94 and the confirmed arithmetic counterexample
was the Q4.12 `roundeven` non-finite overflow described in
`docs/results/2026-08-07-rc-roundeven-q412-equivalence.md`.

## Next diagnostic requirement

Do not change RTL based on this run. Add or select a trace-capable fixture for
one context that records semantic checkpoints and scratch ports 93/94 with
cycle numbers, then rerun under the same frozen oracle and cycle contract.
