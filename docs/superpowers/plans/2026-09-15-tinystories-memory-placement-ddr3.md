# TinyStories-1M selectable BRAM/DDR3 memory placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proven, selectable BRAM/DDR3 backend for immutable TinyStories-1M weights without changing the compiler’s model or arithmetic contract.

**Architecture:** The compiler emits placement metadata on logical memories before technology mapping. An out-of-tree Yosys pass lowers each selected memory to either the existing BRAM implementation or a latency-aware UberDDR3 adapter; activations and state remain BRAM. Equivalence is established first on one projection table, then on the complete weight image and token-level inference.

**Tech Stack:** Python compiler scripts inside Nix, MLIR/RTLIL metadata, out-of-tree Yosys plugin/pass, SystemVerilog, UberDDR3, Yosys, nextpnr-xilinx, Verilator, YPCB/JTAG.

**Spec:** `docs/superpowers/specs/2026-09-15-tinystories-memory-placement-ddr3-design.md`

## Global Constraints

- Use the exact authenticated TinyStories-1M model and existing W8A8 Q16.16/Q8.24 contract.
- Preserve ascending signed-64-bit wrapping MAC semantics and frozen token references.
- Keep the validated UberDDR3 two-lane 333/83.33 MHz profile unchanged.
- Keep PCIe out of the first backend-equivalence milestone; use JTAG for loading/diagnostics.
- Move immutable weights first; runtime activations, context, accumulators, and control remain BRAM.
- Every development build must produce an artifact or diagnostic within 30 minutes; full builds within two hours.
- Retain the BRAM backend and its passing simulations as a regression.

---

### Task 0: Falsify or support DDR3 feasibility before backend implementation

**Files:**
- Create: `scripts/analysis/tinystories_ddr3_feasibility.py`
- Create: `tests/test_tinystories_ddr3_feasibility.py`
- Create: `docs/results/2026-09-15-ddr3-feasibility.md`

**Interfaces:**
- Input is the existing BRAM-mode ordered weight-read trace and the validated UberDDR3 profile.
- Output is a receipt containing reads/token, locality, reuse distance, replay observations, simple prefetch/cache estimates, and measured full-image JTAG load time.

- [ ] **Step 1: Write trace-analysis tests.** Use a deterministic trace to verify read counting, burst-locality calculation, reuse-distance calculation, and load-time accounting.
- [ ] **Step 2: Extract the real trace.** Instrument the current BRAM compiler simulation at the logical memory boundary; do not invent a synthetic access pattern.
- [ ] **Step 3: Replay the trace.** Run it against the measured two-lane 333/83.33 MHz UberDDR3 behavior and record no-cache, simple-prefetch, and small-cache observations.
- [ ] **Step 4: Measure loading.** Time a complete immutable weight-image load over the existing JTAG path and record the image hash before and after readback.
- [ ] **Step 5: Run a minimal integration probe.** Synthesize a compiler-controller plus DDR3-adapter shell to expose obvious timing/routing pressure before full integration.
- [ ] **Step 6: Decide.** Mark the result `supported`, `supported-with-prefetch`, or `not-reasonable` based on observed correctness and practical workflow behavior. Do not compare against a preset bandwidth or latency threshold.
- [ ] **Step 7: Commit.** Commit the feasibility receipt before implementing placement metadata.

### Task 1: Inventory and freeze the logical-memory baseline

**Files:**
- Inspect: `scripts/pipeline/lower_fixed_point_model_to_calyx.py`
- Inspect: `scripts/pipeline/lower_fixed_point_mlp_crossing_to_calyx.py`
- Inspect: `tests/test_bram_bank_geometry.py`
- Create: `docs/results/2026-09-15-memory-placement-baseline.md`

**Interfaces:**
- Consumes the existing authenticated model manifest and generated RTLIL/Futil artifacts.
- Produces a named list of logical memories, widths, depths, initialization hashes, and BRAM-mode reference hashes.

- [ ] **Step 1: Record current declarations.** Enumerate the q/k/v/out and c_fc/c_proj memories, their widths/depths, read latency, and current packing metadata in the baseline document.
- [ ] **Step 2: Capture reference hashes.** Run the existing focused compiler/packing tests inside Nix and record the generated memory-image and four-token boundary hashes.
- [ ] **Step 3: Verify the baseline.** Run `nix develop -c pytest -q tests/test_bram_bank_geometry.py` and the existing production-focused test command; record the exact commands and results.
- [ ] **Step 4: Commit.** Commit the baseline receipt before changing placement interfaces.

### Task 2: Define and emit placement metadata

**Files:**
- Modify: `scripts/pipeline/lower_fixed_point_model_to_calyx.py`
- Modify: `scripts/pipeline/lower_fixed_point_mlp_crossing_to_calyx.py`
- Modify: `tests/test_bram_bank_geometry.py`
- Create: `tests/test_memory_placement_contract.py`

**Interfaces:**
- `projection_memory_placement(model_manifest, mode: str) -> dict[str, dict]` returns complete placement records for `bram` or `ddr3`.
- `emit_memory_placement_attrs(memory, record) -> None` attaches the record to generated RTLIL/Futil metadata.

- [ ] **Step 1: Write failing schema tests.** Assert required fields, valid spaces, integer widths/depths, explicit latency, alignment, address map, and source hashes.
- [ ] **Step 2: Implement the record builder.** Derive records from existing logical memories; reject unknown modes and reject DDR3 placement for writable runtime state.
- [ ] **Step 3: Emit provenance.** Include the placement records and a canonical JSON hash in the existing provenance receipt.
- [ ] **Step 4: Run tests.** Run `nix develop -c pytest -q tests/test_memory_placement_contract.py tests/test_bram_bank_geometry.py`.
- [ ] **Step 5: Commit.** Commit only the metadata/schema change and its tests.

### Task 3: Implement the common memory protocol and DDR3 adapter model

**Files:**
- Create: `rtl/memory/llm_memory_if.sv`
- Create: `rtl/memory/llm_ddr3_adapter.sv`
- Create: `sim/memory/ddr3_latency_model.sv`
- Create: `tests/test_memory_protocol.py`

**Interfaces:**
- `llm_memory_if` exposes `read_req`, `read_resp`, `write_req`, and `write_ack` with explicit cycle-valid signals.
- `llm_ddr3_adapter` accepts logical word addresses and emits ordered responses while driving the validated UberDDR3 request interface.

- [ ] **Step 1: Write protocol tests.** Cover reset, back-to-back reads, variable response latency, writes with byte masks, and no response reordering.
- [ ] **Step 2: Implement the cycle model.** Model fixed initialization plus bounded variable latency and burst assembly; assert that each response matches the requested logical address.
- [ ] **Step 3: Implement the adapter shell.** Convert logical word addresses to the existing UberDDR3 byte/bank mapping and expose a single outstanding-request policy initially.
- [ ] **Step 4: Run simulation tests.** Run `nix develop -c pytest -q tests/test_memory_protocol.py` and the repository’s RTL simulation target for the adapter.
- [ ] **Step 5: Commit.** Commit the protocol and adapter model before integrating generated memories.

### Task 4: Add the out-of-tree Yosys placement pass

**Files:**
- Create: `tools/yosys/llm_memplace.cc`
- Create: `tools/yosys/README.md`
- Create: `tests/test_yosys_memory_placement.py`
- Modify: `flake.nix`

**Interfaces:**
- Yosys command: `llm_memplace -mode bram|ddr3 -manifest <placement.json>`.
- Consumes RTLIL `$mem` cells plus placement metadata; produces a backend-specific wrapper while preserving logical port names and initialization data.

- [ ] **Step 1: Write a minimal RTLIL fixture test.** The fixture contains one read-only memory and checks that `-mode bram` selects BRAM and `-mode ddr3` selects the adapter, with metadata preserved.
- [ ] **Step 2: Implement manifest validation.** Reject missing logical names, shape mismatches, unsupported writes, and inconsistent address maps before rewriting cells.
- [ ] **Step 3: Implement BRAM selection.** Route `bram` records through the current mapping path without changing generated netlist semantics.
- [ ] **Step 4: Implement DDR3 selection.** Replace only eligible immutable memories with the adapter wrapper and emit a machine-readable transformation receipt.
- [ ] **Step 5: Build and test in Nix.** Add the plugin to the development environment and run `nix develop -c pytest -q tests/test_yosys_memory_placement.py`.
- [ ] **Step 6: Commit.** Commit the pass and fixture tests separately from model changes.

### Task 5: Prove one projection table equivalent in BRAM and DDR3 modes

**Files:**
- Create: `tests/test_projection_memory_equivalence.py`
- Create: `sim/memory/projection_equivalence_tb.sv`
- Create: `docs/results/2026-09-15-projection-memory-equivalence.md`

**Interfaces:**
- Testbench input is one authenticated projection-table image and a deterministic ordered address trace.
- Receipt contains BRAM/DDR3 response hashes, first mismatch cycle/address, and tool versions.

- [ ] **Step 1: Generate the trace.** Use the compiler’s existing projection packing helper to produce addresses covering row starts, lane boundaries, burst boundaries, and repeated reads.
- [ ] **Step 2: Run both backends.** Simulate the same trace against BRAM and DDR3 adapters and assert identical `(cycle-independent logical address, data)` sequences.
- [ ] **Step 3: Check initialization.** Compare image hashes before the first request and after readback; fail if any byte differs.
- [ ] **Step 4: Record diagnostics.** On mismatch, report the earliest request/response divergence and classify address mapping, latency/order, or data corruption.
- [ ] **Step 5: Commit.** Commit the passing single-table equivalence receipt and harness.

### Task 6: Integrate full immutable weights and preserve BRAM regression

**Files:**
- Modify: `scripts/pipeline/gen_tiny_stories_selftest_top.py`
- Modify: `rtl/tinystories_1m_ypcb_bram_production_top.sv`
- Modify: `rtl/tinystories_1m_ypcb_bram_top.sv`
- Create: `tests/test_full_weight_backend_selection.py`
- Create: `docs/results/2026-09-15-full-weight-backend-equivalence.md`

**Interfaces:**
- Compiler mode flag selects `bram` or `ddr3` and emits one complete provenance receipt.
- Both modes expose the existing accelerator control/token interface unchanged.

- [ ] **Step 1: Generate BRAM mode.** Rebuild the authenticated full design and require existing four-token and 16-token simulation references to pass.
- [ ] **Step 2: Generate DDR3 mode.** Place only immutable weight tables externally; keep activations/state in BRAM and record the resulting memory map.
- [ ] **Step 3: Run full-image load/readback.** Hash every immutable table after loading through JTAG and compare against source hashes.
- [ ] **Step 4: Run token simulations.** Compare one-token then exact 16-token outputs and all existing boundary checkpoints across both modes.
- [ ] **Step 5: Commit.** Commit only after both modes pass the simulation and hash gates.

### Task 7: Close implementation timing and perform hardware acceptance

**Files:**
- Modify: existing YPCB build targets and constraints only where required to instantiate the selected backend
- Create: `docs/results/2026-09-15-ddr3-hardware-acceptance.md`

**Interfaces:**
- Build outputs include bitstream hash, placement manifest hash, resource report, timing report, and board log.

- [ ] **Step 1: Synthesize both modes.** Run the existing Nix/Yosys flow at the declared clocks; stop before nextpnr if resource reports exceed device limits.
- [ ] **Step 2: Route both modes.** Run constrained nextpnr-xilinx with the fixed project profile and record the first timing/resource failure.
- [ ] **Step 3: Validate standalone DDR3.** Execute the established UberDDR3 initialization/BIST/readback protocol before programming the integrated image.
- [ ] **Step 4: Run three cold starts.** Program the DDR3 image, load the full weight image over JTAG, run the frozen prompt, and compare token-by-token output and runtime.
- [ ] **Step 5: Preserve BRAM acceptance.** Run the same three-run ladder for BRAM mode as a regression, without changing its known-good artifact.
- [ ] **Step 6: Commit receipts.** Commit reports and logs only when they are complete and accurately classify any failure.

### Task 8: Document decision and optional PCIe follow-up

**Files:**
- Create: `docs/adr/2026-09-15-memory-placement-backend.md`
- Modify: project scope/index documentation

**Interfaces:**
- ADR records whether DDR3 is accepted, rejected, or deferred and why; it references immutable receipts rather than informal claims.

- [ ] **Step 1: Summarize evidence.** Include resource, timing, bandwidth, latency, equivalence, and cold-start results.
- [ ] **Step 2: Apply stop/go criteria.** If DDR3 cannot pass single-table equivalence or full-image correctness, record the exact blocker and retain BRAM as the deliverable.
- [ ] **Step 3: Define PCIe follow-up.** Only after DDR3/JTAG acceptance, specify PCIe as a transport substitution with no accelerator or memory-semantic changes.
- [ ] **Step 4: Commit the ADR and index update.**
