# RC context-0 diagnostic at the 600,000-cycle deadline

The strict observable fixture was compiled from the canonical closure and run
with the frozen one-context oracle.  The RTL deadline was 600,000 cycles; the
host runner was allowed 30 minutes per attempt.

The run reached a real result at cycle 523,575 (therefore this is not a host
timeout):

```text
CASE_FAIL index=0 reason=RAW_CODE cycles=523575
expected_codes=18,-93,-34,7,20,1 observed_codes=13,-107,-52,3,11,6
expected_token=4 observed_token=0 write_mask=111111
```

The closure's scratch boundary port 94 contains the exceptional values
`0x84`/`0x7f`; port 93 carries finite Q4.12 values.  The realized closure at
`/nix/store/yk48hnxvmbqih77v4f6a1kqxkrj8cqn2-…` still emitted:

```systemverilog
assign out = left + right;
```

in `std_add`, so `INT32_MIN + (-1)` wraps.  The repository already contains
the justified repair helper `fix_sv_roundeven_overflow.py`; applying it to the
same SV changes exactly one assignment and produces receipt schema
`rc-roundeven-overflow-fix-v1`.  The pipeline now asserts that the guarded
assignment and receipt are present, preventing a stale unpatched closure from
being accepted as repaired.  Unit tests and shell syntax checks pass.

The canonical Nix rebuild was attempted but did not complete within the
available interactive build session, so exact post-fix Verilator equivalence
and frozen-four verification remain outstanding.  This goal is not complete.
