# Exact TinyStories MLP Crossing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the exact block-0 TinyStories-1M MLP crossing in one generated Calyx/SV run.

**Architecture:** Capture a four-row authenticated MLP fixture, prove the existing exact LUT/interpolated GELU in generated SV, then generate one component joining c_fc, GELU, and c_proj through only hardware memories.

**Tech Stack:** Python via `nix develop`, exact PyTorch adapter, Calyx 0.7.1, Verilator `--public-flat-rw`, Yosys, unittest.

**Spec:** `docs/superpowers/specs/2026-09-04-exact-tinystories-mlp-crossing-design.md`

## Global Constraints

- Use prompt `[7454, 2402, 257, 640]`, four block-0 rows, c_fc 64→256, exact fixed GELU, and c_proj 256→64.
- Authenticate fixture/schema at lower and harness time. Host code preloads only immutable source inputs, weights, scales, biases, and LUT.
- Preserve ascending signed i64 wrapping MAC, Q8.24/Q16.16 arithmetic, signed-magnitude half-up rounding, Q16.16 bias, and signed-i8 saturation.
- Generate exactly one `main`; intermediate c_fc/GELU/c_proj values travel through generated hardware memories. Use `-d cell-share` only for staged arithmetic.
- Complete attempt cap: two evidence-backed full compositions; no full-model, board, DDR3, PCIe, RC, generic-SCF, arbitrary-PyTorch, or copied-RTL claim.

---

### Task 1: Authenticated MLP fixture

**Files:**

- Create: `TinyStories/capture_fixed_point_mlp_crossing_slice.py`
- Create: `tests/test_tinystories_1m_fixed_point_mlp_crossing.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json`

**Interfaces:** Produces `capture() -> dict[str, Any]`, `verify_fixture(path: Path) -> dict[str, Any]`, and `verify_fixed_point_replay(path: Path) -> None`.

- [ ] **Step 1: Write the failing replay test**

```python
def test_mlp_fixture_replays_every_boundary(self):
    fixture = capture_mlp.verify_fixture(FIXTURE)
    capture_mlp.verify_fixed_point_replay(FIXTURE)
    self.assertEqual(fixture["slice"]["c_fc"], {"rows": 4, "inputs": 64, "outputs": 256})
    self.assertEqual(fixture["slice"]["c_proj"], {"rows": 4, "inputs": 256, "outputs": 64})
```

- [ ] **Step 2: Run RED**

Run `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_mlp_crossing -v`; expect missing capture module/fixture.

- [ ] **Step 3: Capture exact tensors**

Capture c_fc QDQ entries 24:30 and accumulator 4, GELU nonlinear observation 3, and c_proj QDQ entries 30:36 and accumulator 5 from authenticated `_execute`; also capture both weight codes/scales/biases and the complete 8192-entry GELU LUT. Each record includes semantic name, shape, canonical hash, raw little-endian i64 hash, byte length, and fixture receipt binding.

- [ ] **Step 4: Verify GREEN**

Run `nix develop -c python TinyStories/capture_fixed_point_mlp_crossing_slice.py --output artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json --verify` and the Task-1 unittest; expect eager and integer replay of every boundary.

- [ ] **Step 5: Commit**

Commit `feat: capture exact fixed point MLP crossing fixture` with exactly the capture module, fixture, and test.

### Task 2: Exact generated-SV GELU

**Files:**

- Create: `scripts/pipeline/lower_fixed_point_mlp_crossing_to_calyx.py`
- Modify: `tests/test_tinystories_1m_fixed_point_mlp_crossing.py`

**Interfaces:** Produces `generate_gelu_kernel(fixture_path: Path) -> CalyxArtifact` and `run_gelu_sv(artifact: CalyxArtifact, fixture_path: Path) -> dict[str, object]`; Task 3 consumes the hardware `gelu_q16_16` memory.

- [ ] **Step 1: Write failing generated-SV GELU test**

```python
def test_generated_sv_observes_exact_fixed_gelu(self):
    observed = lowerer.run_gelu_sv(lowerer.generate_gelu_kernel(FIXTURE), FIXTURE)
    self.assertEqual(observed["gelu_q16_16"], tensor_values(FIXTURE, "gelu_q16_16"))
```

- [ ] **Step 2: Run RED**

Run `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_mlp_crossing.MlpCrossingTest.test_generated_sv_observes_exact_fixed_gelu -v`; expect absent generator/runner.

- [ ] **Step 3: Implement exact LUT/interpolation hardware**

Emit `q12=clamp(round_shift_signed(q16,4),-32768,32767)`, index/fraction/upper, LUT interpolation, and `<<4` result exactly as the spec. Preload only input and LUT; observe result memory. Re-check fixture authority before Futil/harness generation and compile with `-d cell-share`.

- [ ] **Step 4: Verify GREEN**

Run the focused test; expect all 1024 hardware-observed GELU values and raw-byte hash to equal the fixture.

- [ ] **Step 5: Commit**

Commit `feat: observe exact fixed GELU in SV` with lowerer and test changes.

### Task 3: One-component c_fc → GELU → c_proj receipt

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_mlp_crossing_to_calyx.py`
- Create: `scripts/pipeline/run_fixed_point_mlp_crossing_sv.py`
- Modify: `tests/test_tinystories_1m_fixed_point_mlp_crossing.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-sv-receipt.json`

**Interfaces:** Produces `run_composed_mlp_sv(fixture_path: Path) -> dict[str, object]`; receipt carries fixture/schema authority, component count, cycles, all observed hashes, artifact hashes, and self-hash.

- [ ] **Step 1: Write failing composition test**

```python
def test_one_generated_sv_main_matches_every_mlp_checkpoint(self):
    receipt = lowerer.run_composed_mlp_sv(FIXTURE)
    self.assertEqual(receipt["execution"]["component_count"], 1)
    self.assertEqual(receipt["observed"]["c_fc_accumulator_sha256"], tensor_hash(FIXTURE, "c_fc_accumulator_i64"))
    self.assertEqual(receipt["observed"]["gelu_sha256"], tensor_hash(FIXTURE, "gelu_q16_16"))
    self.assertEqual(receipt["observed"]["c_proj_codes_sha256"], tensor_hash(FIXTURE, "c_proj_codes_i8"))
```

- [ ] **Step 2: Run RED**

Run `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_mlp_crossing.MlpCrossingTest.test_one_generated_sv_main_matches_every_mlp_checkpoint -v`; expect absent composed runner.

- [ ] **Step 3: Generate direct-memory component and receipt**

Emit `c_fc GEMV -> c_fc rescale/bias/QDQ -> GELU -> c_proj input QDQ -> c_proj GEMV -> c_proj rescale/bias/QDQ`. Assert Futil contains one `component main`; harness contains no c_fc accumulator, GELU result, c_proj input, or expected-output preload. Serialize a canonical self-hashed receipt after matching every simulator-read memory.

- [ ] **Step 4: Verify all acceptance gates**

Run `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_mlp_crossing -v` and `nix develop -c python scripts/pipeline/run_fixed_point_mlp_crossing_sv.py --fixture artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json --composed --yosys-stat`; expect all intermediate/final hashes, receipt self-hash, and same-Futil synthesis Yosys stat.

- [ ] **Step 5: Commit**

Commit `feat: prove exact MLP crossing in generated SV` with lowerer, runner, test, and receipt.

## Self-Review

Task 1 authenticates/replays every fixture boundary; Task 2 proves fixed GELU; Task 3 proves direct-memory composition and receipt. No task substitutes host arithmetic for an observed hardware value, and each interface named by a later task is produced by an earlier task.
