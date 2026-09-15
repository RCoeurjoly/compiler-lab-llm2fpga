# TinyStories-1M DDR3 feasibility preflight

## Status

This is the first Task 0 artifact for the selectable BRAM/DDR3 backend. It is
a compiler-schedule feasibility result, not DDR3 or board evidence. The
measured UberDDR3 replay, JTAG load timing, and minimal routed integration
remain outstanding.

## Exact schedule extraction

The analyzer consumes the compiler’s fixed projection dimensions (eight
layers; q/k/v/out 64×64; c_fc 256×64; c_proj 64×256) and the production LM
head’s four-INT8-lanes-per-32-bit-word layout. For generation steps 1, 2, and
16 it emits a lossless run-length encoding of every logical immutable-weight
visit in compiler order. The full-16 receipt contains 8,848 contiguous runs,
85,217,536 logical word reads, and 123,814,912 payload bytes. Its schedule
hash is:

```text
533fa153f3c6ec5f08cea652b508f7a3b8f1af5b6c92bf70332ab0714d7ac28c
```

Per generated token, the schedule visits context lengths 4 through 19. The
first token performs 2,376,976 logical reads (4,789,312 payload bytes); the
last performs 8,275,216 reads (10,687,552 payload bytes). More than 99.98%
of each step’s consecutive logical accesses are adjacent, because each GEMV
row and the packed LM-head row is sequential. Projection-table addresses are
reused once per context row with a 393,216-read distance in this schedule.

## Interpretation

The pinned UberDDR3 source qualification confirms the target profile:
two byte lanes, 333 MHz DDR3, 83.333 MHz controller clock, `BIST_MODE=2`,
and seed-15 as the working implementation anchor. The existing standalone
Icarus workload was launched with that source closure, but its legacy DRAM
model emits very large command traces and was stopped before a clean
request/ACK latency receipt was produced. Therefore no measured DDR3 latency
or throughput is claimed here.

As a bounded integration-pressure probe, Yosys 0.66 elaborated and optimized
the existing `rtl/rc-working/rc_ddr3_adapter.sv` in 0.06 seconds. The result
contains 40 cells and 322 public wire bits, with no generic memories or
unresolved hierarchy. This is useful evidence that the adapter shell is small;
it is not evidence that the full compiler controller plus DDR3 can route or
meet timing.

The compiler schedule has strong burst locality, but this artifact does not
yet establish attainable DDR3 throughput, adapter latency, JTAG load time, or
timing/routing feasibility. Those are the next required measurements. No
bandwidth or latency threshold is assumed; the eventual decision is whether
the measured implementation is functionally correct and reasonable for the
inference workflow.

## Reproduction

```text
nix develop -c python scripts/analysis/tinystories_ddr3_feasibility.py \
  --steps 16 \
  --output artifacts/diagnostics/tinystories-1m-ddr3-feasibility.json
```
