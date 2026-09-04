# TinyStories-1M Stateful Token-Step Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compiler-owned stateful two-transaction wrapper around the verified four-row block-0 Calyx/SV design.

**Architecture:** Reuse the existing block-composition lowerer and generated Futil as the datapath. Add only a transaction shell, explicit input/output state memories, and a receipt/test harness proving the second invocation consumes the first hardware-produced state.

**Tech Stack:** Python, fixed-point PyTorch oracle, Calyx, Verilator, Yosys, Nix.

**Spec:** `docs/superpowers/specs/2026-09-04-tinystories-token-step-design.md`

## Global Constraints

- Preserve the exact TinyStories-1M fixed-point arithmetic and four-row block fixture.
- Emit one generated Calyx/SV `main`; do not use copied reference RTL.
- Keep simulation and synthesis on the same Futil bytes.
- Do not add embeddings, remaining blocks, final LayerNorm, LM head, token selection, board, DDR3, PCIe, or Representative Core scope.

### Task 1: Stateful wrapper and deterministic two-transaction acceptance

**Files:**
- Create: `scripts/pipeline/lower_fixed_point_token_step_to_calyx.py`
- Create: `scripts/pipeline/run_fixed_point_token_step_sv.py`
- Create: `tests/test_tinystories_1m_fixed_point_token_step.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-token-step-sv-receipt.json`
- Modify: existing block lowerer only where required to expose a compiler-owned state-memory boundary.

**Interfaces:**
- Consumes: `generate_block_kernel(...)` and the authenticated block-composition fixture.
- Produces: `generate_token_step_kernel(...)`, `run_token_step_sv(...)`, and a self-hashed receipt containing `start`, `valid`, `done`, reset, two transaction records, state hashes, Futil/SV/harness hashes, and Yosys resource evidence.

- [ ] **Step 1: Write the failing test** asserting the generated top-level interface, two transaction records, and second-transaction input hash equal the first transaction output hash.
- [ ] **Step 2: Run the focused test under `nix develop -c python`; confirm it fails because the token-step API and receipt do not exist.
- [ ] **Step 3: Implement the smallest wrapper around the existing block kernel.** Keep the block datapath unchanged; make `start`/`valid` gate input capture, commit output state before `done`, and connect the second transaction's input memory to the first transaction's output state in the generated harness.
- [ ] **Step 4: Run the focused test and exact CLI; require bit-exact two-transaction hashes, reset isolation, one generated `main`, and no host expected-output preload.
- [ ] **Step 5: Compile the same Futil to simulation and synthesis SV, run Yosys, and write the self-hashed receipt.
- [ ] **Step 6: Run the relevant regression suite and `scripts/agent/pre_final_check.sh`.
- [ ] **Step 7: Commit the implementation and report evidence, limitations, and the commit hash.
