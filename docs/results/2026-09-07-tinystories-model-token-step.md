# Exact TinyStories-1M model token-step evidence

The generated model-level Calyx/SystemVerilog main produced tokens `[11, 612]`
from the frozen prompt `Once upon a time` (`[7454, 2402, 257, 640]`). The first
selected token was appended by hardware and consumed by the second embedding
lookup. The same simulator process repeated both steps after reset, with
identical boundaries and 450,904,028 cycles per run.

## Execution and independent audit

The saved execution completed in 6,918.306 seconds within its 7,200-second
budget. Task 4 did not rerun this simulation. Its independent audit checked:

- All 64 transcript events in order: isolation, 14 boundaries and token
  selection per step, then completion, for both runs.
- All 56 snapshot files against the authenticated oracle, using both raw
  little-endian int64 hashes and shaped semantic tensor hashes. Boundaries
  include embeddings, all eight blocks, final LayerNorm, and full/last logits.
- Exact feedback contexts, cycle ordering, reset/idle/invalid isolation, and
  equality of both runs, rejecting unknown, missing, or duplicate events.
- Every source binary rematerialized from the authenticated model package;
  no intermediate or second-token preload. The saved harness and visibility
  configuration equal current compiler-generated versions.
- Missing default `.dat` initialization for all 104 external memories, so
  Calyx's optional default loading supplied no hidden intermediate values.
- Saved build commands, logs, executable, Futil, and SV identities. Recompiling
  simulation SV from the saved Futil reproduced the saved SV byte-for-byte.

The full saved-run audit and bounded synthesis capture are reproducible with:

```sh
nix develop -c python scripts/pipeline/audit_fixed_point_model_evidence.py --timeout 1800
nix develop -c python scripts/pipeline/audit_fixed_point_model_evidence.py --verify-only
nix develop -c python -m unittest tests/test_tinystories_1m_model_evidence.py -v
```

The capture and verification commands require the local saved artifacts under
`/tmp/llm2fpga-tinystories-model-bank-local-v1`; the committed receipts retain
their identities and observations, not the large generated RTL or snapshots.

## Same-Futil synthesis and resource scope

Both simulation and synthesis consume Futil SHA-256
`ed7abe873d1a95a0896473acad7467004cc168606b7aac30b1bbdf6c3672509a`.
Synthesis uses the existing block policy `--synthesis --disable-verify`:
simulation-only guard assertions are suppressed; the RTL is not hand-edited.
Calyx synthesis and Yosys 0.66 hierarchy checking passed.

| RTLIL hierarchy metric | Exact count |
| --- | ---: |
| Cells | 14,066 |
| Memories | 104 |
| Memory bits | 137,506,592 |
| Processes | 852 |

Counts come from Yosys `read_verilog -sv; hierarchy -check -top main; stat`
and exact `stat -json` output. This is **before** `proc`, optimization, memory
mapping, or technology mapping. These are not FPGA LUT/FF/BRAM/DSP utilization
numbers and do not establish board fit, timing closure, or place-and-route.

This milestone composes an exact-model generated schedule with existing
fixed-point arithmetic templates. It does not demonstrate arbitrary
PyTorch/torch-mlir full-graph lowering. There is no board execution, DDR3,
PCIe, Representative Core substitution, or copied kev-gpt RTL claim.

## Durable evidence

- [Saved execution receipt](../../artifacts/reference/tinystories-1m-model-sv-execution-receipt.json)
- [Self-hashed independent audit and same-Futil synthesis receipt](../../artifacts/reference/tinystories-1m-model-same-futil-evidence.json)
- [Exact model oracle](../../artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json)

The audit receipt records the verifier and tool identities, original execution
receipt identity, both runs' events and all 56 snapshot records, authenticated
source-file records, bounded synthesis stages, exact JSON resource statistics,
and explicit claim exclusions. Its verifier rejects rehashed resource/claim
tampering and can re-audit every local saved file without rerunning simulation.
