# TinyStories-1M 16-token Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan inline, task-by-task, with verification and commits.

**Goal:** Extend the passing full-model first-token image to exact autonomous
16-token generation across three independent YPCB SRAM configurations.

**Architecture:** Reuse the compiler-owned generation loop and shared transformer
datapath. Prove the existing two-step mode first, then extend context geometry,
authenticated checkpoint coverage, and indexed token readback to sixteen steps.
The host supplies only the frozen prompt and control/readback transactions.

**Tech Stack:** Python inside Nix, Calyx, generated SystemVerilog, Yosys,
nextpnr-xilinx, Project X-Ray, openFPGALoader, existing FTDI JTAG transport.

**Spec:** `docs/superpowers/specs/2026-09-09-tinystories-16-token-board-design.md`

## Global Constraints

- Full compiler-generated TinyStories-1M; no reduced model or RC substitution.
- Preserve exact model/fixed-point arithmetic; no host-generated feedback/state.
- On-chip BRAM/LUTRAM, 30 MHz, JTAG; no DDR3 or PCIe.
- Preserve the first-token image and its raw acceptance/localization artifacts.
- Fixed nextpnr seed 15 and unchanged XDC; explicitly partial BRAM/DSP timing.
- Sixteen exact tokens in <=300 seconds, three independent SRAM configurations.
- Python inside Nix; explicit process deadlines, logs, hashes, and exit statuses.
- Commit verified changes; do not commit a failed checkpoint without approval.

## Task 1: Existing two-token board checkpoint

**Files:** Existing `scripts/pipeline/run_bram_production_sv.py`,
`lower_fixed_point_model_bram_production.py`,
`prepare_tinystories_1m_bram_image.py`, `map_flattened_memory_checkpoints.py`,
`fpga/synthesis/tinystories_signed_dsp_policy.ys`; new
`scripts/pipeline/infer_tinystories_generation_jtag.py` and
`tests/test_tinystories_generation_jtag.py`.

**Interfaces:** Consume `generate_production_kernel(generation_steps=2)` and
the authenticated `[11, 612]` prefix. Produce a separately named two-step
simulation, static image, mapped design, bitstream, and board receipt.

- [x] Revalidate existing production/harness contracts: 19 tests passed.
- [x] Revalidate the full predecessor generation authority with its existing
  verifier; sixteen tokens and context lengths 4..19 authenticated.
- [ ] Inspect archived build scripts and reconstruct the source-to-native-memory
  sequence for new generated SV; never edit the optimized one-step checkpoint
  into a two-step design. Apply the DSP policy before packing in every fresh
  relevant Yosys process. Record commands/versions and hashes in the new output.
- [ ] Generate/execute the existing two-step production source in a fresh output
  directory with an explicit outer bound:

  ```sh
  timeout 7200 nix develop . -c python scripts/pipeline/run_bram_production_sv.py \
    /tmp/tinystories-two-token-board-20260909 --generation-steps 2
  ```

  Require both reset/restart runs, both indexed token outputs, source-only
  preloads, and exact `[11, 612]`. Preserve the resulting provenance and logs.
- [ ] Add failing checker tests for token 1 wrong despite token 0 correct,
  reordered output indices, missing done, repeated START/reset, and invalid
  prompt readback. The new `infer_generation(..., expected_tokens, timeout)`
  returns a raw transaction receipt and requires every token, not only token 0.
- [ ] Implement indexed readback over the existing CSR, without changing the
  first-token checker or providing feedback from the host. Run the new tests
  and existing first-token/USER1 suite inside Nix; commit on green.
- [ ] Materialize the static image with `--generation-steps 2`, execute the
  recovered synthesis recipe, audit signed products and initialized memories,
  route at fixed settings, and generate the bitstream. Use 40-minute routing
  and 12-minute frame-conversion bounds. No acceptance from incomplete output.
- [ ] Program SRAM and require `[11, 612]` after one START. Bind program and
  inference receipts; inspect generated feedback wiring and simulation context
  traces before claiming that the second token consumed the first.

## Task 2: Successor sixteen-step semantic fixture

**Files:** New `TinyStories/capture_fixed_point_continuation_oracle.py`,
`tests/test_tinystories_fixed_point_continuation_oracle.py`, and
`artifacts/reference/tinystories-1m-fixed-point-continuation-oracle.json`.
Consume unchanged helpers/authority from
`TinyStories/capture_fixed_point_model_token_step_oracle.py` and
`scripts/comparison/verify_tinystories_1m_exact_generation.py`.

**Interfaces:** New `build_continuation_oracle(...) -> dict` and
`verify_continuation_oracle(value: dict) -> None`. Preserve the existing
two-step schema/fixture/verifier. New fixture covers sixteen canonical steps.

- [ ] Write failing mutation tests: changed context entry, selected token,
  intermediate hash, model identity, missing step, and host intermediate input.
  All must raise rather than rewriting their hashes into an accepted fixture.
- [ ] Reuse authenticated `_capture_step` arithmetic, with the context updated
  only from its computed selected token:

  ```python
  context = list(prompt)
  steps = []
  for index in range(16):
      step = capture._capture_step(bundle.model, context, index, canonical[index])
      steps.append(step)
      context.append(step["selected_token"]["value"])
  ```

  Bind predecessor identity and capture-source hashes; reference tokens remain
  comparisons, not inputs to the candidate computation.
- [ ] Run verifier/mutation tests, capture the full fixture with a two-hour
  bound, verify all contexts and prefix equality to the immutable old fixture,
  and commit the passing successor evidence.

## Task 3: Compiler-owned generation geometry and output ABI

**Files:** `scripts/pipeline/lower_fixed_point_model_to_calyx.py`,
`lower_fixed_point_model_bram_production.py`, `run_bram_production_sv.py`,
`prepare_tinystories_1m_bram_image.py`; `rtl/tinystories_1m_jtag_csr.sv`,
`rtl/tinystories_1m_ypcb_bram_production_top.sv`; production/harness/CSR tests.

**Interfaces:** Preserve legacy `generation_steps=1|2`. Add 16 with successor
oracle selection. Central geometry has rows, row-address width, context-length
width, step-counter width, output-index width, and each derived buffer size.

- [ ] Add failing tests for steps=16, terminal count 16, output index 15, row
  index 19, and context append length 20; retain all old one/two-step tests.
  Check invalid step counts are rejected.
- [ ] Compute geometry from explicit limits, preserving legacy capacities:

  ```python
  rows = max(8, 4 + generation_steps)
  row_index_width = (rows - 1).bit_length()
  row_counter_width = rows.bit_length()  # must represent the terminal bound
  context_length_width = rows.bit_length()
  step_counter_width = max(2, generation_steps.bit_length())  # preserve legacy width
  token_index_width = max(1, (generation_steps - 1).bit_length())
  ```

  Use these values for all dependent memory dimensions, address expressions,
  copy loops, attention loops and counters. Audit emitted Calyx for residual
  legacy row/step constants, without modifying fixed arithmetic generators.
- [ ] Parameterize the wrapper/CSR output-index width with a legacy-compatible
  default. For sixteen outputs, select command bits `[3:0]`; leave prompt
  index/value fields unchanged. Extend CSR simulation through index 15.
- [ ] Extend harness output arrays, seen-step tracking, and reference loading
  to sixteen. Never preload selected tokens or activation/context feedback.
  Record actual context writes for comparison against the successor fixture.
- [ ] Run geometry, source-image, CSR, checker, and legacy tests; compare legacy
  emitted contracts before/after. Commit the verified compiler/ABI extension.

## Task 4: Sixteen-step generated-RTL semantic acceptance

**Files:** The production runner/harness and successor fixture from Tasks 2–3;
new result artifacts and semantic receipt under a distinct 16-token directory.

**Interfaces:** Consume generated sixteen-step Calyx/SV plus immutable source
tensors. Produce sixteen actual selected-token events and ordered checkpoint
evidence, including FPGA-style context feedback and output-port reads.

- [ ] Extend runner CLI choices to `(1, 2, 16)` with fixture-specific validation.
  Add a failing test that corrupts token/context feedback at step 2 and requires
  the first mismatch to be reported, rather than checking only the final token.
- [ ] Execute bounded compilation and simulation. Require all sixteen tokens,
  contexts, checkpoint hashes, and output-index reads to match. Exercise reset
  and repeat inference without reloading mutable golden state.
- [ ] If a mismatch occurs, preserve exact generated source and observation,
  identify the earliest divergent semantic checkpoint, reproduce it in a
  focused test, and apply only an evidence-backed correction.
- [ ] Commit the successful simulation receipt and source/provenance bindings.

## Task 5: Full-model board implementation and final acceptance

**Files:** Existing synthesis/physical recipes; generation checker; new tracked
`artifacts/reference/tinystories-1m-sixteen-token-board-acceptance.json` and a
dated `docs/results/` summary. Raw results remain in a distinct ignored directory.

- [ ] Materialize source-only static initialization for sixteen steps; verify
  exact weights/scales and policy application before synthesis.
- [ ] Synthesize/map, audit signed multiplication and immutable memory contents,
  and report actual BRAM/LUTRAM/LUT/FF/DSP resources. If fit fails, identify the
  responsible structures before proposing any storage/schedule restructuring.
- [ ] Route with unchanged clock/XDC and seed 15; require legal routing and
  covered-path 30 MHz pass. Preserve the BRAM/DSP timing-coverage disclaimer.
- [ ] Convert frames/bitstream within declared bounds and record all hashes.
  Preserve the accepted first-token bitstream; do not overwrite BPI flash.
- [ ] Run three separate SRAM programming/inference pairs. Require one START,
  no subsequent host prompt/context writes, all sixteen exact outputs, done,
  and <=300 seconds each. Preserve and localize any mismatch before rebuilding.
- [ ] Audit raw receipts and actual process exits; commit the complete evidence
  and limitations after review. Mark the goal complete only for sixteen-token
  simulation and three board passes, never for the two-token checkpoint alone.

## Plan self-review

The five tasks cover authority, feedback, context growth, generated interfaces,
simulation, fit/timing, physical execution, preservation, and final receipts.
The successor fixture avoids invalidating historical authority by editing its
capture source. Full-context recomputation deliberately avoids a new KV-cache
architecture. General-prompt usability and full timing qualification are
explicit exclusions, not implied by a frozen-sequence pass.
