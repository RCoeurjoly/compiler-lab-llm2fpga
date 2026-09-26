# Compiler-Generated RC Phase Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and simulate one autonomous three-token RTL design from the three authenticated compiler-generated W4A8 RC phases.

**Architecture:** Validate the existing phase memory ABI, namespace the three generated SV components, then generate a small control and memory-service shell that passes the hardware-computed token and raw cache words between phases. Compare the completed shell's 237 readback words and three tokens with the frozen integrated PyTorch observation.

**Tech Stack:** Python 3.11 under Nix, PyTorch 2.9.1 exported programs, MLIR flat-SCF metadata, Calyx-generated SystemVerilog, Verilator, unittest, Nix derivations.

**Spec:** [2026-09-26-rc-compiler-phase-composition-design.md](../specs/2026-09-26-rc-compiler-phase-composition-design.md)

## Global Constraints

- Preserve the authenticated W4A8 phase programs, the frozen prompt `[0, 1, 2, 3, 4, 5, 0, 1]`, the three-phase order, four native `f32` cache leaves, and 237-word readback ABI.
- The transformer arithmetic comes exclusively from each phase's compiler-generated SV. No kev-gpt RTL or handwritten model arithmetic enters the composed implementation.
- Keep the previously validated PCIe transport, UberDDR3 two-lane 333/83.33 MHz profile, clocks and constraints untouched in this plan.
- Use bounded compilation and simulation. A tool timeout or signal-9 kill is recorded separately from a semantic mismatch.
- Run Python tests inside `nix develop`; use Nix inputs for persistent generated artifacts. Commit each verified change separately and leave the worktree clean.

## Review Focus

- Module identifiers inside comments or signal names: namespace only definitions and instantiation types; test both cases in Task 1.
- Generated helper modules that differ between phases: namespace every defined module; test same-name/different-body sources in Task 1.
- A phase's output cache differing from the next input in width or shape: reject in Task 2 before generating SV.
- Negative floating logits and ties: hardware argmax must match lowest-index PyTorch selection; test in Task 3.
- Reset during cache transfer or a second `start` while busy: clear or reject deterministically; test in Task 3.

---

### Task 1: Namespace the compiler-generated phase modules

**Files:**
- Create: `scripts/pipeline/namespace_rc_phase_sv.py`
- Create: `tests/test_namespace_rc_phase_sv.py`

**Interfaces:**
- Consumes: one Calyx-native `main.sv` and a phase prefix.
- Produces: `namespace_modules(source: str, prefix: str) -> tuple[str, dict]`, with a manifest of original/renamed module names and input/output SHA-256.

- [ ] **Step 1: Write tests** for a parameterized helper instance, duplicate helper names with different bodies in two phases, a signal named like a module, and comments containing module names. Require a renamed `main_1` and unchanged signal/comment text.
- [ ] **Step 2: Run** `nix develop --impure -c python -m unittest tests.test_namespace_rc_phase_sv`; expect failure for the missing function.
- [ ] **Step 3: Implement** token-aware module declaration and instantiation type rewriting. Reject duplicate definitions, unsupported syntax and missing `main_1`.
- [ ] **Step 4: Rerun the tests**, then namespace all three authenticated phase SV artifacts and run bounded Yosys `read_verilog -sv; hierarchy -check -top <renamed_main_1>` for each.
- [ ] **Step 5: Commit** the code and test after verification.

### Task 2: Build a typed phase handoff manifest

**Files:**
- Create: `scripts/pipeline/build_rc_phase_handoff.py`
- Create: `tests/test_build_rc_phase_handoff.py`
- Reuse: `scripts/pipeline/verify_rc_serving_phase_abi.py` and `scripts/pipeline/run_rc_serving_w4a8_sv.py`

**Interfaces:**
- Consumes: frozen compiler phase ABI, each phase flat SCF, exported program and namespaced SV receipt.
- Produces: `build_handoff(...) -> dict`, specifying token input/output ports, last-logit offset and six-word width, cache source/destination ports and exact word counts, readback bindings, initial-memory images, and hashes.

- [ ] **Step 1: Write tests** that accept prefill output ports 33..36 to decode-8 input ports 28..31 and decode-8 output ports 33..36 to decode-9 input ports 28..31, then reject one altered width, depth, leaf order or source hash.
- [ ] **Step 2: Run focused tests** and confirm the intended red failure.
- [ ] **Step 3: Implement** the manifest using the existing flat-SCF/SV parsers and exported-program tensor serialization; derive the prefill last-logit offset from shape rather than a hard-coded value.
- [ ] **Step 4: Verify** with focused tests and the three authenticated phase artifacts; compare every handoff tensor's byte hash with the frozen chained export receipt.
- [ ] **Step 5: Commit** the verified manifest builder and tests.

### Task 3: Generate the autonomous RTL shell

**Files:**
- Create: `scripts/pipeline/generate_rc_phase_composed_shell.py`
- Create: `tests/test_generate_rc_phase_composed_shell.py`

**Interfaces:**
- Consumes: Task 1 namespaced SV and Task 2 typed handoff manifest.
- Produces: `render_shell(manifest: dict) -> str`, memory images, source file list, and a hash-bound receipt. The top exposes reset, eight prompt writes, `start`, busy/done/error, three tokens and 237-word readback.

- [ ] **Step 1: Write a synthetic three-phase RTL test** that proves prompt loading, phase order, generated token feedback, byte-preserving cache copies, reset isolation, busy-start rejection and all readback addresses.
- [ ] **Step 2: Run it with Verilator** and confirm the missing shell fails.
- [ ] **Step 3: Generate** the three phase instances, registered memory-service logic, one-element-per-cycle cache copy, finite-f32 lowest-index argmax, controller and readback mux. Reject invalid generated manifest fields.
- [ ] **Step 4: Rerun the synthetic simulation** and focused Python tests; run Yosys hierarchy on the generated top.
- [ ] **Step 5: Commit** the generator and tests.

### Task 4: Run the real compiler-generated equivalence gate

**Files:**
- Modify: `flake.nix` to expose a phase-composed RC shell derivation and bounded simulation receipt.
- Modify: `scripts/pipeline/run_rc_serving_w4a8_integrated_sv.py` to consume the composed shell's source list and report phase/port/word/bit at first mismatch.
- Create: `docs/results/2026-09-26-rc-phase-composed-equivalence.md`

**Interfaces:**
- Consumes: the pinned three authenticated phase artifacts and Tasks 1-3.
- Produces: a reproducible Nix shell plus a bounded exact simulation receipt, including the three tokens, all 237 readback words and source/provenance hashes.

- [ ] **Step 1: Write a focused runner test** that detects the earliest mismatching readback word and distinguishes compile timeout, simulator signal 9 and functional mismatch.
- [ ] **Step 2: Run the red test**, implement the runner and Nix package, then run the focused test again.
- [ ] **Step 3: Build and simulate** under a declared time and memory bound. If the real design does not reach simulation, retain a durable diagnostic receipt and localize the failed stage.
- [ ] **Step 4: Verify** exact token and readback evidence if simulation runs; record logs, durations and hashes. Do not claim PCIe/DDR3 or hardware completion from this task.
- [ ] **Step 5: Commit** only after the exact gate passes or the user explicitly authorizes a failed diagnostic checkpoint.

## Follow-on integration

The active goal continues after this plan: connect the verified generated
phase shell's memory provider to the validated PCIe/UberDDR3 loader, prove
image load/readback and controller calibration/BIST, then obtain fit, timing
closure, bitstream and three cold-start YPCB runs. If the three-core resource
report exceeds YPCB capacity, a later compiler optimization must share
arithmetic or memory across phases while preserving this equivalence gate.
