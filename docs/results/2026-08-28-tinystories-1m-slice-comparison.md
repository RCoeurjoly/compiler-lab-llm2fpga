# TinyStories-1M compiler/reference slice comparison

Date: 2026-08-28

## Result

The comparison result is **incomplete**, not a functional or efficiency
claim.  The checked-in compiler slice manifest reports
`source_artifact_unavailable`: no full TinyStories-1M compiler-generated RTL
artifact was found by its deterministic discovery policy.  Therefore no
reference/compiler checkpoint pair, final token pair, Yosys resource receipt,
or nextpnr timing receipt exists for the selected slice.

The machine-readable receipt is
[`tinystories-1m-slice-comparison.json`](../../artifacts/comparison/tinystories-1m-slice-comparison.json).
It pins the reference contract and the slice-manifest hashes and leaves
resources, timing, and the provenance-linked waste map null/empty.

## Gate semantics

The harness accepts only these statuses:

- `contract_mismatch`: model/package/quantization identity differs.
- `functional_mismatch`: exact named checkpoint tensors or final tokens
  differ.
- `aligned`: contract, checkpoint tensors, final tokens, resources, and
  timing evidence are all present and match where required.
- `incomplete`: any required evidence is unavailable.  No efficiency delta or
  waste candidate is emitted in this state.

Once the full compiler artifact is produced, provide explicit reference and
compiler evidence JSON files containing their frozen contracts, exact
checkpoint tensors, final tokens, resource measurements, timing measurements,
and provenance annotations.  Each evidence side must bind to the exact Task 1
contract SHA-256 and its whole semantic contract (including ABI and frozen
reference fields).  The public API verifies the manifest binding against the
supplied, on-disk frozen-contract SHA-256.  Empty checkpoint/token/report data is incomplete evidence,
never an aligned result.  Every aligned resource/timing input must provide a
report path, SHA-256, and measurement identifier.  The harness preserves them
when parsing Yosys and nextpnr receipts.  A waste-map entry requires an exact,
positive per-entry measured delta (not a clipped estimate), a compiler stage,
module, source operation, and the matching compiler resource measurement
identifier; it is never inferred from module naming alone.

Side-to-side output agreement is also insufficient: both final output sequences
must equal the frozen Task 1 reference token sequence.

The existing `yosys-slang` structural-utilization receipt is intentionally not
treated as FPGA LUT/FF/BRAM/DSP data.  Its memory-bit and cell-type statistics
are retained as structural statistics, while unavailable technology-mapped
resources remain `null`.

The parser also recognizes standard Yosys `stat -json` module counts at
`modules.<top>.num_cells_by_type`, while keeping structural counts distinct
from a technology-mapped resource report.
