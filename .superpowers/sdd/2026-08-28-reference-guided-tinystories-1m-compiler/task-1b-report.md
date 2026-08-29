# Supplemental Task 1b report: exact-input identity frontier

## Status

`authenticated`.  The canonical audit selects only the accepted-spec frozen
`fixed_hardware_reference` profile, reports no identity conflicts, and advances
the next gate to `exact_quantized_pytorch_model`.

The absence of an internal board checkpoint trace is recorded as the explicit
`board_checkpoint_trace_unavailable` observability limitation.  It is not
reported as an identity conflict and this report makes no claim that such a
trace exists.

## Evidence inspected

- Accepted spec: `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`, SHA-256 `99632d030170ceaf0194b8f41c1fa784f262bb82d4f33f35f5fe90f2b4926bfc`.
- Canonical package and its receipt at
  `/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m`:
  all eleven receipt-listed files were checked by SHA-256 and size, including
  the manifest, weights, scales, calibration IDs, tokenizer JSON, vocabulary,
  and merges.  The model revision is
  `ac533fb8b4f69c71894bf96badfe11e6294d9fcf`; tokenizer JSON is
  `f6ed3d307010c244c22aeffbde05f419cf277c23e64cf98b673cac5449cfeff5`.
- Pinned kev-gpt revision `df1fc45b2ffcb26fddc19cfd57621e7eedf6153f`, with
  clean source paths and hashes for package generation, integer/fixed runtime,
  RTL fixture, resident GEMV RTL, iterative divider RTL, and host transport.
- The fixed executable reference was run through Nix and generated the frozen
  16 IDs from prompt IDs `[7454, 2402, 257, 640]`:
  `[11, 612, 373, 257, 1310, 2576, 3706, 20037, 13, 1375, 6151, 284, 711, 2354, 287, 262]`.
- All semantic artifacts were inspected and content-bound in the v2 contract:
  Q/DQ receipt `a274d61ec5f634fac8fb501339ddfe7ae4bf774d950840498d54c32b90d79e77`,
  historical selector receipt
  `756627744bf1e3f8dcab27e9d0accbe9a1ab38d93a73fbbbb01557c08470819b`,
  and selected fixed profile
  `f3fa88e8af4982a0e189a3887cd256d207d4c0a891ec587ab3b11b069785c9a6`.

## Red / green record

Red before production changes:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_input_audit.py -v
FAIL: expected authenticated, got identity_frontier
```

Additional focused red checks confirmed the missing fail-closed adapter-input
function and the missing canonical semantic-receipt hash binding.

Green verification:

```text
nix develop -c python -m unittest -v \
  tests.test_tinystories_1m_exact_input_audit \
  tests.test_tinystories_1m_reference_input \
  tests.test_tinystories_1m_reference_contract \
  tests.test_tinystories_1m_qdq_semantics \
  tests.test_tinystories_1m_fixed_hardware_qdq_profile \
  tests.test_tinystories_1m_implementation_profile
40 tests passed
```

The canonical audit was then regenerated deterministically with:

```text
nix develop -c python scripts/comparison/audit_tinystories_1m_exact_input.py \
  --contract artifacts/reference/tinystories-1m-exact-input-contract.json \
  --package /home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m \
  --kev-root /home/roland/kev-gpt/.worktrees/kintex-selftest \
  --output artifacts/reference/tinystories-1m-exact-input-audit.json
authenticated
```

`git diff --check` passed.

## Files changed

- `scripts/comparison/audit_tinystories_1m_exact_input.py`
- `tests/test_tinystories_1m_exact_input_audit.py`
- `artifacts/reference/tinystories-1m-exact-input-contract.json`
- `artifacts/reference/tinystories-1m-exact-input-audit.json`

## Artifact status

The v2 contract contains the complete package-file identities, tokenizer hash,
per-output/per-channel INT8 profile, Q16.16 and Q8.24 formats, signed 64-bit
serial GEMV accumulator, source hashes, prompt IDs, and expected 16 tokens.
The canonical audit file SHA-256 is
`3ad018a7d9edd94c91c9c0f9698477d645bed49c56094b4745cd38901912ceea`;
its payload SHA-256 is
`d8b5b58493fe914571a2444a74b0dae0b47bc42d90743ab93e93faa0bfb8a19f`.

The finite-only fixed domain is verified by checking activation scales,
scale-image floats, and materialized FP32 package tensors.  Adapter values are
fail-closed: NaN and either infinity are rejected before entering the integer
datapath.

## Commit

Pending at report creation; filled after verified commit.

## Concerns

- No content-bound internal YPCB checkpoint trace is available.  This remains
  a board-observability limitation for later functional/hardware gates, not an
  identity conflict at Gate 0.
- The legacy Q/DQ and implementation-selector artifacts retain their historical
  `incomplete`/`unresolved` statuses because they are bound to the superseded
  historical contract.  The exact-input v2 contract binds them as historical
  evidence while explicitly selecting the accepted deployed fixed profile.
