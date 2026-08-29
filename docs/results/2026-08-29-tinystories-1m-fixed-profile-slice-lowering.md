# TinyStories-1M fixed-profile slice lowering result

Status: `unsupported` / `unaligned`

The authenticated Task 3l package export was inspected as a real
`torch.export` program.  The first operation in transformer block 0 is graph
node 149, `aten.layer_norm.default`, corresponding to `block.ln_1`.

The selected fixed-hardware profile precisely defines the per-channel Q8.24
activation conversion, signed half-away rounding and saturation, ascending
signed-64 serial accumulation, per-output weight scaling, and post-scale bias
order.  It does **not** define the fixed-point LayerNorm mean/variance widths
and reduction order, epsilon representation, inverse-square-root algorithm,
or gamma/beta rounding, saturation, and overflow.  The recorded
`block.input` and `block.ln_1.output` tensors are examples for one frozen
input; they cannot define LayerNorm for other values.

The compiler therefore fails closed at `block.ln_1` with
`fixed_layer_norm_semantics_unavailable`.  It emits no MLIR, SystemVerilog, or
RTLIL and does not run or claim compiler-slice equivalence.  The twelve stored
software checkpoints are hash-validated as the authenticated profile trace;
the reference implementation was not rerun as part of this compiler probe.
Board authentication remains unresolved.

## Evidence

- authenticated exported program SHA-256:
  `389964a2f39a8256bc824b58b60f681bd136f2868633125e8872ce9791c8e73e`
- exported graph call-function count: `394`
- exported operation-sequence SHA-256:
  `571e331e1886c16576560cb7e09069eee0a5eb8a2700ede1215c635485f559ac`
- Task 2 metadata status: `contract_mismatch`; it is retained and hashed, not
  relabelled as a usable compiler RTL slice
- machine-readable result:
  `artifacts/comparison/tinystories-1m-fixed-profile-slice-lowering.json`

No kev-gpt source or RTL was copied.  The reference remains a
content-authenticated behavioral oracle, and LLM-assistance disclosure remains
required.
