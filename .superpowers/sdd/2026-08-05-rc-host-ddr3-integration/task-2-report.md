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
`27..45`), in ABI order.  It requires the exact source image and manifest,
checks the image hash bound by the Calyx receipt, and uses each authoritative
source-segment offset as the logical byte address.  It never invents a dense
packed DDR address space.  Each bound row retains byte order, source segment,
and raw Calyx tensor hash where available; the manifest explicitly lists every
local port exclusion (token, output, and mutable scratch).

The mapping also authenticates the exact image-manifest bytes against the
`image_manifest_sha256` in the Calyx receipt before reading any offsets; a
caller cannot re-point segment offsets by supplying a replacement manifest.

When a Task 1 source closure is supplied, the audit requires its declared
UberDDR3 checkout and invokes Task 1's `verify_manifest`, rejecting stale or
tampered source files instead of accepting SHA-shaped fields.

Tests run:

```text
python3 -m unittest tests.test_rc_ddr3_compatibility tests.test_rc_ddr3_mapping -v
python3 -m py_compile scripts/pipeline/audit_rc_ddr3_compatibility.py scripts/pipeline/generate_rc_ddr3_mapping.py
git diff --check -- scripts/pipeline/audit_rc_ddr3_compatibility.py scripts/pipeline/generate_rc_ddr3_mapping.py tests/test_rc_ddr3_compatibility.py tests/test_rc_ddr3_mapping.py
```

All passed (twelve focused unit tests).  Immutable learned ports now require
the canonical proven-zero write-enable evidence; a rehashed forged mutable
write-enable digest rejects.

Concern: no generated RC receipt artifact is currently retained in this
worktree.  The utilities therefore support both receipt forms and are covered
with schema-faithful synthetic receipts; Task 3 must invoke them against the
actual strict RC materialization before compiling the adapter.  The existing
ABI/binding receipt schema contains no completion trace, so its single-request
completion rule is an adapter constraint pending Task 3 transport evidence,
not a measured timing claim.
