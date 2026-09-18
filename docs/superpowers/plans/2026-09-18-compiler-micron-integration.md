# Compiler/Micron DDR3 Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> for inline execution, or superpowers:subagent-driven-development when
> delegation is authorized. Steps use checkbox syntax for tracking.

**Goal:** Prove the current compiler accelerator with actual UberDDR3/PHY and
Micron-model memory, then qualify consolidation and first-token board inference.

**Architecture:** Retain the passing owner-mux harness boundary and compiler
candidate. Replace its transaction-memory double with the pinned DDR controller,
PHY and pin-level Micron model; inject host traffic at Wishbone, not PCIe.

**Tech Stack:** Nix Python, Icarus or XSim for vendor-model compatibility,
SystemVerilog, existing compiler lowering, Yosys and nextpnr-xilinx.

**Spec:** `docs/superpowers/specs/2026-09-18-compiler-micron-integration-design.md`

## Global Constraints

- No kev-gpt RTL, model/arithmetic changes, calibration bypass or memory preload.
- Preserve two-lane 333/83.33 MHz, full 15/10/3 geometry, `MICRON_SIM=0`, BIST 2.
- Preserve PCIe, physical DDR3 and timing constraints; disclose Wishbone injection.
- Development commands have a 1,800-second wall bound; full runs use explicit
  budgets informed by measured runtime, with no silent extensions.
- Keep persistent test sources/receipts in the repository, scratch outputs in
  unique directories, and commit verified changes. Do not launch routing now.

### Task 1: Verify the exact simulation profile and model elaboration

**Files:** create `tests/test_compiler_micron_profile.py`,
`sim/compiler_ddr3/sim_defines.vh`, `sim/compiler_ddr3/micron_profile_tb.sv`,
and `scripts/analysis/run_compiler_micron_sim.sh`.

**Interfaces:** runner accepts `--phase profile|startup|load|infer` and
`--work-dir PATH`; explicit source arguments select pinned UberDDR3, generated
model, vendor parameters and image. It must reject missing inputs rather than
substituting another model. Profile phase terminates after elaborated assertions.

- [ ] Write failing tests for the profile: expected `(rows, columns, banks,
  dq_bits) == (15,10,3,16)`, `MICRON_SIM == 0`, `BIST_MODE == 2`, and clock
  periods `(12000,3000)`. Reject the bundled 16-row-bit default.
- [x] Generate the explicit macro header:
  ```verilog
  `define TWO_LANES_x8
  `define x16
  `define den4096Mb
  `define sg125
  ```
- [x] Compile the pinned Micron model with the authentic 4096-Mbit parameter
  file through an explicit include path. Use `iverilog -g2012 -s micron_profile_tb`
  inside `nix develop .#default -c`; the testbench uses `$fatal` on profile
  mismatch and prints `PASS: micron profile` only after runtime assertions.
- [x] Run the positive profile and wrong-geometry negative control, confirm
  nonzero exit for the latter, record all model/parameter hashes and commit.

Model-only elaboration is verified (three tests). Controller parameters,
production startup and calibration are not covered by this first checkpoint.
See `sim/compiler_ddr3/README.md` for the reproducible command and limitations.

### Task 2: Exercise production startup, calibration and BIST

**Files:** create `sim/compiler_ddr3/uberddr3_micron_memory.sv` and
`sim/compiler_ddr3/startup_tb.sv`; extend the runner and profile tests.

**Interfaces:** memory wrapper exposes the existing 128-bit Wishbone interface,
controller clock/reset and calibration status; internally instantiates pinned
`ddr3_top`, Micron memory and the necessary FPGA primitive models. No inferred
transaction RAM is permitted in this wrapper.

- [ ] Test rejection of missing calibration, model errors and watchdog expiry.
- [ ] Instantiate the exact spec parameters; generate controller/DDR/quadrature/
  reference clocks at their board periods with 1-ps resolution. Keep reset
  release and startup durations observable, not forced internal state.
- [ ] Compile and run `--phase startup` under `timeout --kill-after=10s 1800`.
  Record simulated time, calibration/BIST phase, simulator wall time and backing
  file usage. A timeout is a cost measurement, not a pass.
- [ ] Require natural completion of calibration and full BIST before advancing;
  retain strict model timing diagnostics. Commit only verified harness work.

### Task 3: Replace the abstract memory in the compiler integration harness

**Files:** create `sim/compiler_ddr3/compiler_micron_tb.sv`; extend the runner;
reuse the logical checks in the September 18 owner-mux wrapper/driver.

**Interfaces:** `--image PATH` supplies the authenticated binary to host stimulus;
the DUT receives every byte through controller writes. `--phase load` stops after
complete readback; `--phase infer` adds prompt/START and token validation.

- [ ] Add a negative control that corrupts one host write and requires readback
  failure before START; add an inference watchdog that fails rather than passing
  an incomplete run.
- [ ] Instantiate unchanged command adapter, backend, arbiter and owner mux.
  Port the host handshake checks from `owner-integration-driver.cpp` to the chosen
  simulator, preserving request stability and checking every readback byte.
- [ ] Run load-only with the complete 4,136,720-byte image and verify its SHA-256
  against `tinystories-1m-ddr3-model-image-manifest.json` before stimulus starts.
- [ ] Run infer with `[7454,2402,257,640]`, require token 11, no memory errors,
  balanced completions and retained output under backpressure. Store phase logs
  and source/tool/model provenance; explicitly mark PCIe ingress uncovered.

### Task 4: Consolidation, implementation and hardware qualification

**Files:** compiler externalizer and bank-controller tests described by the
approved consolidation spec; result documents and existing board runner.

- [ ] After Task 3 passes, implement bank consolidation using failing semantic
  tests first. Preserve the 240-slot ABI and per-bank response ownership.
- [ ] Repeat abstract-memory regressions and the exact Task 3 Micron-model
  load/inference gate. Localize the first mismatch before modifying RTL again.
- [ ] Compare synthesis area and request structure against the existing candidate;
  only then run bounded placement/routing at unchanged clocks and seed 15.
- [ ] Require completed qualified route and provenance before bitstream promotion.
  Use the established PCIe recovery/load/readback protocol for board token 11.
  Record timing coverage limitations and do not claim 16-token acceptance.
