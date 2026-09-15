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
model emits very large command traces and was stopped before a new clean
request/ACK latency receipt was produced. An existing pinned UberDDR3 XSim
regression log does provide a measured simulator profile for the same
configuration: 2,304 sequential operations average 12 ns/request (64-byte
payload, 5.333 GB/s effective payload rate), while 2,304 random operations
average 49 ns/request (1.306 GB/s). The source log SHA-256 is
`a78d5c3841d50f3761f7a588095e9d067744fee8645847818dd947bfebf37dd3`; the
normalized receipt is
`artifacts/diagnostics/uberddr3-measured-profile.json`. These are simulator
measurements, not board measurements.

As a bounded integration-pressure probe, Yosys 0.66 elaborated and optimized
a deterministic 256-request controller shell instantiated with the audited
`rtl/rc-working/rc_ddr3_adapter.sv`. The hierarchy contains 64 cells and 608
public wire bits, with no generic memories or unresolved hierarchy. The
provenance receipt is
`artifacts/diagnostics/ddr3-controller-pressure-probe.json`. This is useful
evidence that the controller/adapter shell is small; it is not evidence that
the full compiler controller plus DDR3 can route or meet timing.

The BRAM baseline has no runtime full-image JTAG load operation: immutable
weights are initialized by the bitstream. That requirement is therefore
explicitly marked not applicable to the baseline in
`artifacts/diagnostics/tinystories-1m-jtag-load-applicability.json`. A complete
JTAG load/readback timing must be measured once the DDR3 image-load protocol
exists; no synthetic transfer time is substituted.

The compiler schedule has strong burst locality, but this artifact does not
yet establish attainable DDR3 throughput, adapter latency, JTAG load time, or
timing/routing feasibility. Those are the next required measurements. No
bandwidth or latency threshold is assumed; the eventual decision is whether
the measured implementation is functionally correct and reasonable for the
inference workflow.

The run-length model gives 85,217,536 external requests with no cache. With
eight-word sequential bursts, the same logical schedule requires 10,652,192
burst requests. A 1,024-word cache does not retain a projection table until
its next context-row reuse (the measured schedule distance is 393,216 words),
so this simple cache has the same request count as burst prefetch. These are
request-count estimates only; they are not substituted for measured DDR3
latency or bandwidth. Supplying the measured profile to the analyzer adds
serialized service-time estimates: approximately 1.02 s (no-cache) or 0.128 s
(8-word bursts) under the sequential 12 ns/request profile, and approximately
4.18 s or 0.522 s under the random 49 ns/request profile for the full 16-step
schedule. These estimates exclude compute, overlap, arbitration, and startup;
they are a feasibility bound, not an inference result.

The controller/adapter shell also passes a bounded RTL handshake simulation:
eight deterministic sequential requests complete with eight ordered responses
in 46 cycles under a one-cycle delayed-accept behavioral model. The receipt is
`artifacts/diagnostics/ddr3-controller-pressure-probe-sim.json`. This validates
the shell’s request/response accounting only; the behavioral model is not a
substitute for the UberDDR3 controller or board.

An attempted replay through UberDDR3’s built-in Icarus `+replay_trace` hook did
not reach its `DONE_CALIBRATE` gate, so it produced no replay pass or latency
measurement. This is recorded as an inconclusive calibration wait in
`artifacts/diagnostics/uberddr3-bounded-replay-attempt.json`; it is not treated
as either DDR3 failure or success.

After restoring the exact validated profile in an isolated testbench copy, the
same replay hook passed all four ordered transactions. The measured completion
latencies were 5, 9, 5, and 9 controller cycles (60, 108, 60, and 108 ns at
83.333 MHz), including write/read pairs at two sequential addresses. The
provenance receipt is
`artifacts/diagnostics/uberddr3-bounded-replay-profile.json`. This is direct
controller-model evidence, but it is still a four-transaction replay rather
than the complete 85-million-read schedule or board measurement.

## Reproduction

```text
nix develop -c python scripts/analysis/tinystories_ddr3_feasibility.py \
  --steps 16 \
  --profile artifacts/diagnostics/uberddr3-measured-profile.json \
  --output artifacts/diagnostics/tinystories-1m-ddr3-feasibility.json
```
