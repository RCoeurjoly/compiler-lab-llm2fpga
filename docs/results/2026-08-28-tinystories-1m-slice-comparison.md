# TinyStories-1M compiler/reference slice comparison

Date: 2026-08-28

## Result

The comparison result is **`contract_mismatch`**, not a functional or
efficiency claim.  The checked-in metadata records a realized full
TinyStories-1M compiler SV artifact: 310,344,726 bytes with SHA-256
`04b090f78c358757dfca4b56f2d45ee1d05281a8ed9d803ee267ac3000fe9d06`.
The historical build that produced this artifact (source commit
`cc8d7e69edd6e7296be976d84f15b4fc5e4d90ac`) used HuggingFace revision
`77f1b168e219585646439073245fe87e56b3023e`; the frozen kev-gpt contract
requires `ac533fb8b4f69c71894bf96badfe11e6294d9fcf` and its quantized-package
hashes.  This historical receipt is therefore a `contract_mismatch`, and the
strict extractor deliberately made no slice artifact.  The current registry
was subsequently repinned to `ac533…9fcf`; it still requires a fresh full SV
materialization and extraction before it can replace this historical receipt.
Consequently no reference/compiler checkpoint pair, final token pair, Yosys
resource receipt, or nextpnr timing receipt exists for the selected slice.

The machine-readable receipt is
[`tinystories-1m-slice-comparison.json`](../../artifacts/comparison/tinystories-1m-slice-comparison.json).
It pins the reference contract and the slice-manifest hashes and leaves
resources, timing, and the provenance-linked waste map null/empty.  The
published compiler metadata is
[`tinystories-1m-baseline-float-sv-metadata.json`](../../artifacts/comparison/tinystories-1m-baseline-float-sv-metadata.json).

## Gate semantics

The harness accepts only these statuses:

- `contract_mismatch`: model/package/quantization identity differs.
- `functional_mismatch`: exact named checkpoint tensors or final tokens
  differ.
- `aligned`: contract, checkpoint tensors, final tokens, resources, and
  timing evidence are all present and match where required.
- `incomplete`: any required evidence is unavailable.  No efficiency delta or
  waste candidate is emitted in this state.

Before extracting a slice, authenticate one common model revision and package
identity for the compiler and reference.  Then provide explicit reference and
compiler evidence JSON files containing their frozen contracts, exact
checkpoint tensors, final tokens, resource measurements, timing measurements,
and provenance annotations.  Each evidence side must bind to the exact Task 1
contract SHA-256 and its whole semantic contract (including ABI and frozen
reference fields).  The public API verifies the manifest binding against the
supplied, on-disk frozen-contract SHA-256.  Empty checkpoint/token/report data is incomplete evidence,
never an aligned result. Checkpoint values must be finite numeric scalars or
non-empty rectangular arrays; nulls, booleans, ragged arrays, and non-numeric
values are malformed. Every aligned resource/timing input must provide a
report path, SHA-256, and measurement identifier. The harness reparses that
exact hashed Yosys or nextpnr receipt and requires every claimed measurement to
equal its parsed value; the presence of an unrelated hashed file authenticates
nothing. Timing frequencies and path delays must be finite and positive, token
cycles must be positive integers, and interface overhead must be a
non-negative integer no larger than the token cycle count. A waste-map entry requires an exact,
positive per-entry measured delta (not a clipped estimate), a compiler stage,
module, source operation, and the matching compiler resource measurement
identifier; it is never inferred from module naming alone.

Side-to-side output agreement is also insufficient: both final output sequences
must equal the frozen Task 1 reference token sequence.

A `ready` label is not trusted on its own.  Before any comparison, the harness
requires the exact Task 2 schema, TinyStories-1M identity, transformer-block
token-step kind, a non-empty bounded dependency closure, exact artifact coverage,
and matching on-disk hashes for the source metadata, every source file, and every
extracted file.  The source metadata must itself bind the frozen model revision
and package hashes.

Functional evidence uses the canonical
`tinystories-1m-transformer-block-token-step-trace-v1` schema for block 0 and
the final frozen prompt token.  It requires exactly these shaped checkpoints:
block input; layer-normalization 1 output; attention Q, K, V, and output;
attention residual; layer-normalization 2 output; MLP input, activation, and
output; and final block output.  The hidden checkpoints are length 64, Q/K/V
are 16 by 4, and the two intermediate MLP checkpoints are length 256.  Each
tensor and the complete trace carry a verified content hash.  Missing, extra,
malformed, or differently identified traces remain `incomplete`.

Timing claims are accepted only when the hashed receipt parses back to the
same measurement identifier, global and per-clock frequencies, critical-path
clock domain and endpoints, delays, cycles per token, and interface overhead.
Changing a domain or endpoint without changing the authenticated receipt cannot
produce `aligned`.

The existing `yosys-slang` structural-utilization receipt is intentionally not
treated as FPGA LUT/FF/BRAM/DSP data.  Its memory-bit and cell-type statistics
are retained as structural statistics, while unavailable technology-mapped
resources remain `null`.

The parser also recognizes standard Yosys `stat -json` module counts at
`modules.<top>.num_cells_by_type`, while keeping structural counts distinct
from a technology-mapped resource report.

## Task 4 optimization gate

Task 4 is currently **`blocked_missing_evidence`**.  The comparison receipt is
`contract_mismatch`, its functional checkpoints are unavailable, and its
`waste_map` is empty.  There is therefore no ranked, provenance-linked
compiler candidate with measured before/after resource and timing cost.

The fail-closed result is
[`tinystories-1m-optimization-result.json`](../../artifacts/comparison/tinystories-1m-optimization-result.json).
No lowering, scheduling, or template source was modified, and no optimization
claim is made.  The next valid Task 4 attempt requires a fresh aligned slice
comparison, exact functional evidence, and technology-mapped resource and
timing receipts for both sides; structural guesses or an unmeasured change do
not satisfy this gate.
