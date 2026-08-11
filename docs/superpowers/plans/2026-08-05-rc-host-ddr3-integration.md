# Host-only DDR3-backed RC integration plan

> **Status:** Deferred by ADR-0005. Execute this scaling plan only after the
> fully on-chip inference checkpoint and its XC7K480T fit or failure boundary
> have been recorded.

> Implementation plan; execute only after selecting an execution mode.

## Goal

Integrate the frozen V=6 PT2E W8A8 representative core with UberDDR3 in host simulation, while preserving the compiler memory ABI and exact PyTorch equivalence. Only immutable learned tensors use the DDR3 path initially. Token input, mutable activation/scratch memories, and output buffers remain local. No physical board is required for this plan.

## Acceptance gates

1. Pinned source closure: LLM2FPGA revision `5cae9d4c339e151affa43ee0f471da3ba289f3d0`; UberDDR3 revision `4a51b9671347130759c9980d6756918f084e2124`; all RTL/model files and hashes recorded.
2. ABI audit: generated RC `memory-abi.json` and `calyx_memory_bindings` agree with the pinned UberDDR3 Wishbone/user-port contract.
3. Transport microcase: exact read data, logical-to-byte address translation, one-cycle/completion ordering, reset, and backpressure are proven against the host DDR3 model.
4. One-context DDR3-backed RC: six signed int8 logits and lowest-index argmax exactly match the frozen PyTorch oracle, with all checkpoints and a durable receipt.
5. Frozen-four, 24-context, and 64-context campaigns reuse the existing equivalence runner and evidence ladder; no exhaustive simulation is required.

## Files and interfaces

- Create `scripts/pipeline/materialize_ddr3_source_closure.py` and `tests/test_ddr3_source_closure.py`; emit a manifest containing revisions, selected paths, hashes, include paths, macro definitions, and compile order for UberDDR3 RTL and the manufacturer model.
- Create `scripts/pipeline/audit_rc_ddr3_compatibility.py` and `tests/test_rc_ddr3_compatibility.py`; consume `memory-abi.json` and `calyx_memory_bindings`, classify the 146 ports, verify widths/order/outstanding-request assumptions, and emit `ddr3-compatibility.json`.
- Create `scripts/pipeline/generate_rc_ddr3_mapping.py` and `tests/test_rc_ddr3_mapping.py`; consume the compatibility receipts and emit a hash-bound mapping manifest containing only immutable learned-tensor ports, logical addresses, byte layout, and local-port exclusions.
- Create `rtl/rc-working/rc_ddr3_adapter.sv`, `rtl/rc-working/rc_ddr3_host_top.sv`, and `sim/rc-working/rc_ddr3_transport_tb.sv`; implement the bounded adapter and host model seam without changing the generated RC ABI.
- Create `tests/test_rc_ddr3_transport.py`; test reset, reads, address translation, completion ordering, and rejected writes independently of the full RC.
- Modify `scripts/pipeline/run_rc_sv_equivalence.py` only to accept the generated mapping/source-closure manifests and to preserve existing local fixtures for token/input, scratch/activation, and output ports.
- Create `scripts/pipeline/run_rc_ddr3_equivalence.py`, `tests/test_rc_ddr3_equivalence.py`, and `docs/results/2026-08-05-rc-host-ddr3-integration.md`; run one-context, frozen-four, 24, and 64 tiers and record exact results, liveness, timing, source hashes, and counterexamples.
- Add Nix/flake packaging only after the host scripts work; no ambient `/home/roland/UberDDR3` checkout may be an undeclared input.

## Task sequence

### 1. Pin and close sources

Write tests for deterministic manifest generation and missing/hash-mismatched files. Materialize the exact UberDDR3 controller/PHY/top, YPCB wrapper/XDC references, and manufacturer simulation model support files; record include paths, macros, order, and hashes. Verify the manifest independently before invoking Verilator.

### 2. Audit the ABI and derive the mapping

Write failing tests for port count, pin widths, response timing, and unsupported outstanding requests. Parse the existing receipts, classify learned tensors versus local input/scratch/output, and generate the mapping manifest. Reject hand-edited or stale receipts by checking hashes and deterministic serialization.

### 3. Prove the transport seam

Implement the smallest adapter state machine supported by the audit. Exercise a synthetic set of learned-tensor reads through the pinned UberDDR3 user port and manufacturer model. Compare every returned byte and completion event; retain a failing trace for any mismatch.

### 4. Integrate the RC

Generate the host top from the mapping manifest, connect learned-tensor ports to the adapter, and leave all other ports on the existing local fixture. Run the 600,000-cycle first-result bound, then compare six logits, argmax, and semantic checkpoints against the frozen PyTorch reference. Fail fast and emit the existing minimized counterexample packet.

### 5. Run evidence and performance tiers

Run frozen-four, 24, and 64 contexts with the existing corpus and receipt schema. Record compile time, peak memory, cycles/s, first-result cycle, per-context wall time, and tool provenance. Set DDR3-specific wall budgets only after the first successful smoke; do not claim universal equivalence.

### 6. Package and hand off

Add reproducible Nix derivations and a concise result document. The later TinyStories-1M Yosys/nextpnr-xilinx scale probe and closed-loop optimization campaign are separate follow-on plans, gated on this DDR3-backed RC result.

## Verification commands

Run the focused Python tests, source-closure audit, compatibility audit, transport microcase, then the one-context and selected equivalence tiers. Every command must consume only declared manifests and emit machine-readable receipts; a timeout, mismatch, or OOM is retained as a failed candidate rather than discarded.
