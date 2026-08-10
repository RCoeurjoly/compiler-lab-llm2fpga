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

## Regenerated-closure follow-up

The rebuild was subsequently completed at
`/nix/store/ii2d6l6n8b2mqzgxq4amw2his3jnjri2-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv-no-synthesis`.
Its generated SV has the guarded `std_add` and output SHA-256
`9599bd8694d5baf0074306a178e80d9898430091ce13d00455f706916892bff6`.
Verilator compilation completed with 443 C++ files; code generation took
94.48 s and C++ compilation 1,215.20 s.

The repaired closure still failed context 0 at cycle 523,575 with the same
six codes and token.  The repair is observable: scratch port 94 changes from
the old `0x7f` values to `0x80`.  However, scratch port 85 is already
different, so the overflow repair is not the earliest divergence in this
fresh closure.  The Futil SHA is identical to the retained closure
(`fe663546…`), while the regenerated SV contains a materially different
HardFloat primitive-definition closure.  This makes primitive/tool closure
provenance the next investigation target; no equivalence claim is made.

## Divsqrt-handshake repair

The retained passing diagnostic closure showed that `std_divSqrtFN` must issue
one HardFloat request per Calyx transaction and complete on `outValid`. The
fresh Nix closure therefore applies `fix_sv_divsqrt_handshake.py` after the
round-even repair. Receipt:

```text
closure=/nix/store/5qm739maxpd9cvg5jwkdm316s8kr7g35-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv-no-synthesis
sv_sha256=2262298433271af636683517bba9c7641d02097de314b3dac4f4e3c0843e83f7
divsqrt_repair_count=1
```

The strict Verilator context-0 run used the frozen image, manifest, memory
ABI, f32 constant proof, and exact one-record PyTorch oracle. It completed at
cycle 505,273 and passed all six raw logits and the final token:

```text
CASE_PASS index=0 cycles=505273 expected_codes=18,-93,-34,7,20,1 observed_codes=18,-93,-34,7,20,1 expected_token=4 observed_token=4 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111
SHARD_PASS start=0 count=1 completed=1 min_cycles=505273 max_cycles=505273
```

Verilator reported 990.425 s wall time (8-thread CPU time 7919.322 s), which
explains why a one-minute host timeout is not a meaningful equivalence budget.
The repository frozen-four derivation is still running against this same
closure; no multi-context equivalence claim is made until its durable summary
passes.

## Frozen-four and ordered-reset gate

The repaired Verilator binary was run directly from the compile cache
`/tmp/rc-divsqrt-strict/obj_dir/Vtb`, with ABI receipt
`1cd84e6cbfef8400c5b2a9ddf68ba4ad3f734f9f8542eefe252aa56a2c91988b`, the
same generated SV closure, frozen image/manifest, and 600,000-cycle bound.
The four independent frozen oracle shards all passed:

```text
ascending  index=67141   cycles=505036  codes=-28,127,45,-12,-30,-3  token=1
alternating index=239945 cycles=505237  codes=-22,98,34,-10,-23,-3    token=1
zeros      index=0       cycles=505273  codes=18,-93,-34,7,20,1       token=4
descending index=1612474 cycles=504497  codes=19,-97,-35,7,21,1      token=4
```

Each line emitted `CASE_PASS`, `done=1`, `completion_count=1`,
`within_bound=1`, `reset_complete=1`, and `write_mask=111111`. The ordered
single-process sequence used those same four records in the repository order
ascending, descending, zeros, alternating and emitted:

```text
SEQUENCE_PASS count=4 completed=4 resets=4 min_cycles=504497 max_cycles=505273
```

The sequence run took 2,883.794 s wall time (23,068.139 s CPU on eight
threads). The Nix convenience wrapper was stopped after its daemon stalled;
the direct run used the already compiled cache and identical RTL, ABI, image,
oracle records, cycle bound, and exact comparison fixture. This is therefore
the durable functional gate evidence; it does not claim exhaustive
equivalence over the full 1,679,616-context domain.
