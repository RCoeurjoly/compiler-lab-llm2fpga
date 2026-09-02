# Exact TinyStories Serial-GEMV Salvage Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Produce provenance-verified synthesizable SystemVerilog for the exact TinyStories-1M contract through a bounded compiler-owned serial-GEMV route, or record the first bounded causal frontier.

**Architecture:** Preserve the eager model as oracle. Express every ascending signed-64-bit GEMV as an explicit custom boundary rather than exporting its scalarized Python loop; legalize only it against the pinned Torch-MLIR ABI; generate a defined serial Calyx component/invoke; emit SV normally.

**Spec:** docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md

## Global Constraints

- Preserve exact package/model/tokenizer/prompt/16-token reference; 97 activation Q/DQ boundaries; W8 per-output weights; Q16.16/Q8.24; ascending signed-i64 wrapping MAC.
- No DDR3, PCIe, Representative Core, arbitrary-PyTorch generality, copied/wrapped kev-gpt RTL, or unbounded compiler command.
- Stage commands have a 30-minute wall-clock limit; full exact-model build has two-hour maximum. Stop at first failure.
- Run Python only with nix develop -c python and commit every green task.

---

### Task 1: Exact exported serial-GEMV boundary

**Files:** Create TinyStories/serial_gemv_boundary.py, tests/test_tinystories_1m_exact_serial_gemv_export.py, scripts/pipeline/probe_exact_serial_gemv_export.py. Modify TinyStories/model_adapter_exact_package.py.

**Interfaces:** Input is signed-i64 rank-2 scaled activation R×K and W8 codes M×K; output is signed-i64 R×M. Exported name is llm2fpga.serial_gemv.default. Receipt binds eager/export output hashes, exported-program hash, operator count, and frozen GEMV boundary hashes.

- [ ] Write red tests for 64×64, 256×64, 64×256, non-i64 rejection, rank rejection, eager/boundary equality, and exactly one exported operator.
- [ ] Run nix develop -c python -m unittest tests/test_tinystories_1m_exact_serial_gemv_export.py -v. Expected: boundary absent.
- [ ] Implement torch.library.custom_op llm2fpga::serial_gemv. Its eager body moves the present serial loop verbatim into ascending_i64_wrapping_mac; its fake body returns R×M. Change only the adapter call site.
- [ ] Run export tests plus exact eager-generation verification, write receipt, commit feat: export exact serial GEMV boundary.

### Task 2: Pinned Torch-MLIR legalizer

**Files:** Create tools/torch-mlir-passes/LegalizeExactSerialGemv.cpp, tools/torch-mlir-passes/CMakeLists.txt, nix/torch-mlir-passes.nix, tests/test_tinystories_1m_exact_serial_gemv_legalizer.py, reproducers/tinystories-1m-exact-serial-gemv/raw-boundary.mlir. Modify flake.nix, nix/pipeline.nix, scripts/compile-pytorch.py.

**Interfaces:** Raw Torch-MLIR torch.operator torch.llm2fpga.serial_gemv with fixed rank-2 si64 shapes becomes llm2fpga.serial_gemv with rows, outputs, inputs, mac_order=ascending_i64_wrap. Unknown custom operator, dynamic dimension, non-si64, and unknown shape fail with exact_serial_gemv_contract.

- [ ] Write structural test requiring a plugin linked to pinned Torch-MLIR ABI, then reduced-IR test requiring raw custom operator removed and exact compiler op present.
- [ ] Run tests/fixture under timeout 1800. Expected: pass missing or existing illegal torch.operator diagnostic.
- [ ] Implement only the described conversion. Add raw import route and invoke plugin before fixed backend pipeline.
- [ ] Run fixture, source tests, one registered export-to-legalized stage under timeout 1800, bind hashes, commit feat: legalize exact serial GEMV boundary.

### Task 3: Compiler-generated defined Calyx component

**Files:** Create scripts/pipeline/lower_exact_serial_gemv_to_calyx.py, tests/test_tinystories_1m_serial_gemv_calyx.py, reproducers/tinystories-1m-exact-serial-gemv/calyx-component.mlir. Modify nix/pipeline.nix.

**Interfaces:** Legalized descriptors plus compiler-owned memories produce calyx.component @llm2fpga_serial_gemv_M_K and a calyx.invoke per source boundary. The component visits k from zero through K-1 for each output row and emits an ordered trace hash.

- [ ] Write red tests for component/invoke presence, 64×64 ordered trace hash, descriptor rejection without ascending_i64_wrap, and no reference RTL hash match.
- [ ] Run red test. Expected: missing lowerer/component.
- [ ] Generate structural/control IR only from dimensions and descriptor, using explicit i64 multiply/add state/counters. No vector reductions and no reference RTL read.
- [ ] Parse/lower/emits Calyx; run ordered address/data trace and Yosys syntax/stat on all shapes under timeout 1800; commit feat: lower exact serial GEMV to Calyx component.

### Task 4: Bounded full composition and SV provenance

**Files:** Create scripts/pipeline/run_exact_serial_gemv_frontier.py, scripts/pipeline/verify_exact_serial_gemv_frontier.py, tests/test_tinystories_1m_exact_serial_gemv_frontier.py, artifacts/comparison/tinystories-1m-exact-serial-gemv-frontier.json. Modify nix/models.nix and flake.nix.

**Interfaces:** Consume prior receipts and produce one earliest-stage receipt: provenance-closed SV or hash-bound first failure; include tool/input/output/command hashes and elapsed time.

- [ ] Write red test that forced Calyx failure leaves later stages empty and every stage timeout at most 1800 seconds.
- [ ] Implement sequential export, legalize, Calyx, SV, synthesis runner and verifier. Reject timeout, missing output, unknown custom op, and SV source outside compiler closure.
- [ ] Run timeout 7200 nix build --no-link -L .#tiny-stories-1m-exact-serial-gemv-sv. Commit success only if artifacts verify; otherwise retain only verified diagnostic receipt with user approval.

### Task 5: Frozen 16-token completion audit

**Files:** Create scripts/pipeline/verify_exact_serial_gemv_end_to_end.py, tests/test_tinystories_1m_exact_serial_gemv_end_to_end.py, artifacts/comparison/tinystories-1m-exact-serial-gemv-semantic-audit.json.

**Interfaces:** Consume Task 4 SV closure plus oracle and produce self-hashed boundary hashes, frozen token ids, SV/tool/source hashes, synthesis report, and elapsed times.

- [ ] Write red test that any token/boundary-hash mutation is rejected with frozen_token_mismatch.
- [ ] Compare eager, export, legalized, Calyx, and SV traces. Simulation uses generated SV and compiler-owned memories only.
- [ ] Run all suites, nix flake check --no-build, scripts/agent/pre_final_check.sh, and bounded full build. Commit audit. Claim salvage only if every gate passes; otherwise retain first verified frontier.

## Self-review

- Tasks 1–5 cover oracle preservation, ABI-matched legalization, compiler-generated Calyx, bounded provenance/SV, and frozen-token auditing.
- The only custom boundary is rank-2 signed-i64 llm2fpga.serial_gemv with fixed shapes and ascending_i64_wrap. No task permits scope drift.

