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
and provenance annotations.  The harness preserves report paths and SHA-256
hashes when parsing Yosys and nextpnr receipts.  A waste-map entry requires
both a positive measured resource delta and a compiler provenance annotation
with module and source operation; it is never inferred from module naming
alone.
