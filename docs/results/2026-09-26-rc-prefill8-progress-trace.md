# RC prefill-8 bounded progress trace

This diagnostic follows the current repaired compiler-generated native-SV
closure. It is a host-only control-progress observation; it is not an
equivalence or hardware result.

## Method

The generated Verilator binary was run with a line-buffered heartbeat every
1,000 testbench cycles. The heartbeat reports the generated FSM state and the
state of the repeat-104 loop that had appeared near the earlier runtime
frontier. The run was bounded to 300 seconds.

## Evidence

The run reached the suspected region and continued past it:

```text
cycles=34000 fsm=825  idx=8
cycles=38000 fsm=969  idx=8
cycles=52000 fsm=1297 idx=8
cycles=60000 fsm=1504 idx=8
```

The complete line-buffered log is in the throwaway diagnostic directory
`/tmp/rc-prefill8-heartbeat/heartbeat-1k-300s.log` with SHA-256
`3f29d5c956417011044424ef99d3719f9a0947b4cd56236250590100c9d32983`.
The process exited with timeout status 124 at 300 seconds; no `done` or output
files were produced.

## Interpretation

The generated control is advancing: repeat-104 reaches its terminal index and
the FSM proceeds to later states. The current RC prefill failure is therefore
not evidence of a permanent state-722 deadlock. It is an extreme schedule/
simulation-throughput frontier. The current closure advances only tens of
thousands of cycles in several minutes, while its testbench permits up to
100,000,000 cycles. A semantic result remains unverified.

This rules out a speculative fix aimed solely at the state-722 transition. The
next compiler/backend work should reduce generated schedule cost or improve
simulation execution while preserving the exact contract, then rerun the
bit-exact prefill gate.
