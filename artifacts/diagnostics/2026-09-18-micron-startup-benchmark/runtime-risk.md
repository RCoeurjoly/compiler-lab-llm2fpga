# Full-controller simulation runtime risk

This is an intermediate observation, not an acceptance receipt. The running
baseline is described in [full-run-launch.json](full-run-launch.json). Revalidate
its process and terminal artifacts before relying on its current status.

## Observed progress

The unchanged XSim process (PID 1346532) completed the sequential write/read
sweeps and entered `RANDOM_WRITE` (controller state 19). The transition lies
between controller cycles 71,000,000 and 71,100,000. No `FAIL:`, `FATAL:`,
`ERROR:`, `Error:`, or `Fatal:` diagnostics were found at this observation.
Full BIST, image loading/readback, and accelerator inference have not passed.

Read-only samples from `/tmp/compiler-micron-full.nIto9M/run.log`:

| Host observation (Unix UTC seconds) | Latest logged cycles | Random writes |
| --- | ---: | ---: |
| 1789771356 | 71,400,000 | 42,481 |
| 1789771427 | 71,500,000 | 56,110 |
| 1789771443 | 71,600,000 | 69,741 |
| 1789771514 | 71,700,000 | 83,373 |
| 1789771623 | 72,000,000 | 124,260 |

The final sample's process elapsed time was 11:22:47. Host requests,
accelerator requests, and accelerator responses were all zero.

## Estimate, not a measured completion time

The first-to-last samples span 600,000 cycles, 81,779 random writes, and
267 wall-clock seconds. That is about 7.34 controller cycles per random write.
Extrapolating the sampled wall rate over 33,554,432 addresses gives roughly
30 hours for this write phase alone. Logs occur every 100,000 cycles, so
host polling times are not exact simulation-event timestamps; a coarse
30–40-hour planning range is more appropriate than a precise ETA.

Random reads and alternating write/read accesses follow this phase. Their
wall-clock rates have not yet been measured. Complete image loading/readback
and first-token inference follow full BIST. Consequently the existing
72-hour wall limit is at material risk; this is not proof that it will expire.
The one-billion-controller-cycle limit is separate and also remains in force.

## Unchanged scope and next action

No timeout, BIST mode, memory geometry, calibration wait, RTL, or simulation
input was changed for this observation. Do not bypass startup, preload memory,
or treat an advancing counter as acceptance. Preserve this run and measure
subsequent phases; resolve any necessary runtime-budget change explicitly,
without silently extending the limit or restarting the baseline.

The simulation still injects host traffic at Wishbone, not through PCIe.
Behavioral primitives and ideal clocks do not qualify board timing or prove
hardware inference. Compiler bank consolidation and implementation remain
gated on the baseline acceptance result.
