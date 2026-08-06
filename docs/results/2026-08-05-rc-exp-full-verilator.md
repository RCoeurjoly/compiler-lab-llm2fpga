# RC exp-table full Verilator equivalence attempt

## Scope

This run used the generated RC observable fixture with the oracle-backed,
256-entry exp lookup integrated into the explicit SystemVerilog closure. It
was intended to execute one strict oracle context (`shard_start=0`,
`shard_count=1`).

## Reproducibility

- Normalized RTL: `/tmp/rc-fixture-support/work/main.sv`
- Testbench: `/tmp/rc-fixture-support/work/tb.sv`
- Support RTL: `rtl/rc-working/rc_exp_table_lookup.sv`
- Table image: `artifacts/rc_exp_table.hex`
- Verilator: 5.022
- Compile: `--cc --exe --main --timing --Wno-fatal -O0 --output-split 1000 --output-split-cfuncs 1000 --top-module tb`
- Runtime: `+shard_start=0 +shard_count=1 +cycle_bound=1000000`
- Oracle: frozen-four `shard-0-1.hex`
- ABI receipt observed: `sha256=745309f9640d426c3ca262ba6708a01526896c1eea2784c63be6118755165012`

## Result

Verilator C++ generation and linking completed, producing a 60 MiB `Vtb`
executable. The strict simulation emitted the ABI receipt but produced neither
`CASE_PASS` nor `CASE_FAIL` within a 300-second wall-clock timeout (exit status
124). Therefore functional equivalence is **not yet established**. The result
is a reproducible simulation-performance blocker, not an equivalence claim.

## Follow-up heartbeat run

A rebuilt testbench with 1,000-cycle heartbeats completed the first context at
cycle 514,871 and found a concrete mismatch:

```text
CASE_FAIL index=0 reason=RAW_CODE cycles=514871
expected_codes=18,-93,-34,7,20,1 observed_codes=-70,26,22,-112,-39,10
expected_token=4 observed_token=0 write_mask=111111
```

The process exited with status 134 after the testbench assertion. This is now a
functional counterexample, not a simulation-timeout blocker.
