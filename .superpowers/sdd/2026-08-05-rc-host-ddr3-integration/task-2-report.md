# Task 2 report — audit ABI and derive DDR3 mapping

Status: complete.

Files changed:

- `scripts/pipeline/audit_rc_ddr3_compatibility.py`
- `scripts/pipeline/generate_rc_ddr3_mapping.py`
- `tests/test_rc_ddr3_compatibility.py`
- `tests/test_rc_ddr3_mapping.py`
- `.superpowers/sdd/2026-08-05-rc-host-ddr3-integration/task-2-report.md`

The compatibility audit consumes full receipts or the canonical JSON payload
files emitted by the RC runner.  It validates canonical serialization and
SHA-256s, binds Calyx memory bindings to the exact ABI receipt, classifies all
146 ports, and records the fixed memory-service pin directions, in-order
single-outstanding completion contract, and the pinned 128-bit (16-byte)
UberDDR3 Wishbone interface.  It optionally binds the Task 1 source-closure
manifest when supplied.

The mapping generator emits only immutable learned tensor ports (`0..24` and
`27..45`), in ABI order.  Regions are byte-addressed, little-endian, and
16-byte aligned; the manifest retains raw Calyx tensor hashes where available
and explicitly lists every local port exclusion (token, output, and mutable
scratch).

Tests run:

```text
python3 -m unittest tests.test_rc_ddr3_compatibility tests.test_rc_ddr3_mapping -v
python3 -m py_compile scripts/pipeline/audit_rc_ddr3_compatibility.py scripts/pipeline/generate_rc_ddr3_mapping.py
git diff --check -- scripts/pipeline/audit_rc_ddr3_compatibility.py scripts/pipeline/generate_rc_ddr3_mapping.py tests/test_rc_ddr3_compatibility.py tests/test_rc_ddr3_mapping.py
```

All passed (seven focused unit tests).

Concern: no generated RC receipt artifact is currently retained in this
worktree.  The utilities therefore support both receipt forms and are covered
with schema-faithful synthetic receipts; Task 3 must invoke them against the
actual strict RC materialization before compiling the adapter.
