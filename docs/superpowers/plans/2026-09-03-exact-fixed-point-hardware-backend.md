# Exact Fixed-Point Hardware Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the authenticated TinyStories-1M block-0 Q-projection fixed-point `GEMV -> requantization` contract in generated SV and prove every checkpoint bit-for-bit.

**Architecture:** Task 1's fixture and Task 2's schema are the only semantic inputs. Replace the single-MAC structural Calyx artifact with a sequential microkernel, generated external-memory harness, and four gates: observed one-output MAC, complete accumulator trace, exact requantization, and composed result writes. Simulator values, not Python oracle values, are the acceptance evidence.

**Tech Stack:** Python through `nix develop`, Calyx 0.7.1, Verilator `--public-flat-rw`, Yosys, unittest, authenticated JSON receipts.

**Spec:** `docs/adr/2026-09-03-exact-fixed-point-hardware-backend.md`

## Global Constraints

- Verify `artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json` and `artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-schema.json` before generation.
- At each ascending `k=0..63`, form `signed_i8(activation_codes_i8[row][k]) * input_scale_q8_24[k]`, multiply that signed scaled value by `signed_i8(weight_codes_i8[output][k])`, then perform the signed 64-bit wrapping accumulator update. Do not use rounded `activation_q16_16` as the MAC operand. Apply Q8.24/Q16.16 boundaries, signed-magnitude half-up rounding, and signed i8 saturation only as specified by the fixture/schema.
- Generated-SV observations, not `ordered_value_trace` or Python recomputation, are the gate evidence.
- A development stage is capped at 30 minutes and a complete gate at two hours.
- Do not claim full-model/token, board, DDR3, PCIe, Representative Core, generic-SCF, arbitrary-PyTorch, or copied-kev-gpt results.
- Stop after two Gate-1 implementations without the expected first accumulator, or two diagnostics that cannot localize an SV mismatch to memory timing, MAC arithmetic, or harness observation. Write the evidence report required by the spec.

---

### Task 1: Observe one exact 64-MAC output in generated SV

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_schema_to_calyx.py`
- Create: `scripts/pipeline/run_fixed_point_calyx_sv.py`
- Modify: `tests/test_tinystories_1m_fixed_point_schema_calyx.py`

**Interfaces:**

- Consumes: `lower_schema(schema_path: Path, fixture_path: Path) -> CalyxArtifact`.
- Produces: `generate_one_output_kernel(schema_path: Path, fixture_path: Path) -> CalyxArtifact` and `run_generated_sv(artifact: CalyxArtifact, fixture_path: Path, row: int, output: int) -> dict[str, int]`.
- Later tasks depend on simulator-produced `accumulator_i64` and positive `cycles`.

- [ ] **Step 1: Write the failing observed-output test**

```python
def test_generated_sv_observes_first_64_mac_accumulator(self):
    lowerer = load_lowerer()
    artifact = lowerer.generate_one_output_kernel(SCHEMA, FIXTURE)
    observed = lowerer.run_generated_sv(artifact, FIXTURE, row=0, output=0)
    expected = json.loads(FIXTURE.read_text())["tensors"]["gemv_accumulator_i64"]["values"][0][0]
    self.assertEqual(observed["accumulator_i64"], expected)
    self.assertGreater(observed["cycles"], 64)
```

- [ ] **Step 2: Run the test and record the absent-interface failure**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_generated_sv_observes_first_64_mac_accumulator -v`

Expected: FAIL because `generate_one_output_kernel` or `run_generated_sv` is absent.

- [ ] **Step 3: Implement the minimal sequential kernel and harness**

```python
# Futil control invariant:
# seq { init_acc; while k < 64 { read activation_code[row][k], input_scale[k],
#                                and weight[output][k];
#                                scaled = signed_i8(code) * input_scale_q8_24;
#                                acc = wrap_i64(acc + scaled * signed_i8(weight));
#                                k = k + 1; }
#       accumulator_trace[0] = acc; }
# Harness: preload fixture arrays, clock until done, read trace[0] by
# --public-flat-rw, sign-extend it, return {"accumulator_i64": value, "cycles": cycles}.
```

Invoke the Task-1 and Task-2 verifiers before writing Futil. Reject fixture
tensor byte hashes, lengths, or expected memory shapes that do not match.

- [ ] **Step 4: Run observed-SV and structural checks**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_generated_sv_observes_first_64_mac_accumulator -v && nix develop -c python scripts/pipeline/run_fixed_point_calyx_sv.py --schema artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-schema.json --fixture artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json --row 0 --output 0`

Expected: PASS; JSON names generated Futil/SV/harness artifacts and reports the exact first accumulator and positive cycle count.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_schema_to_calyx.py scripts/pipeline/run_fixed_point_calyx_sv.py tests/test_tinystories_1m_fixed_point_schema_calyx.py
git commit -m "feat: observe exact fixed point GEMV output in SV"
```

### Task 2: Observe the complete 4x64 accumulator trace

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_schema_to_calyx.py`
- Modify: `scripts/pipeline/run_fixed_point_calyx_sv.py`
- Modify: `tests/test_tinystories_1m_fixed_point_schema_calyx.py`

**Interfaces:**

- Consumes: Task 1 preloader and signed trace ABI.
- Produces: `generate_full_gemv_kernel(schema_path: Path, fixture_path: Path) -> CalyxArtifact` and `run_full_gemv_sv(artifact: CalyxArtifact, fixture_path: Path) -> dict[str, object]` with row-major `accumulator_trace_i64: list[int]` and `trace_sha256: str`.
- Later tasks use the observed 256 values as the only GEMV input to requantization.

- [ ] **Step 1: Write the failing full-trace test**

```python
def test_generated_sv_observes_full_row_major_accumulator_trace(self):
    lowerer = load_lowerer()
    observed = lowerer.run_full_gemv_sv(lowerer.generate_full_gemv_kernel(SCHEMA, FIXTURE), FIXTURE)
    fixture = json.loads(FIXTURE.read_text())
    expected = [x for row in fixture["tensors"]["gemv_accumulator_i64"]["values"] for x in row]
    self.assertEqual(observed["accumulator_trace_i64"], expected)
    self.assertEqual(observed["trace_sha256"], fixture["tensors"]["gemv_accumulator_i64"]["sha256"])
```

- [ ] **Step 2: Run the test to demonstrate missing full-kernel execution**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_generated_sv_observes_full_row_major_accumulator_trace -v`

Expected: FAIL because the full-kernel generator/runner is absent.

- [ ] **Step 3: Emit explicit row/output/k counters and trace writeback**

```text
for row = 0..3, output = 0..63, k = 0..63 in that exact nesting/order:
  scaled := signed_i8(activation_code[row][k]) * input_scale_q8_24[k]
  acc := wrap_i64(acc + scaled * signed_i8(weight_code[output][k]))
after each k-loop: trace[row * 64 + output] := acc
```

The Verilator harness reads all 256 entries and hashes the documented
little-endian signed-64-bit byte sequence; it must not call `serial_gemv`.

- [ ] **Step 4: Verify trace and synthesis structure**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_generated_sv_observes_full_row_major_accumulator_trace -v && nix develop -c python scripts/pipeline/run_fixed_point_calyx_sv.py --schema artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-schema.json --fixture artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json --full-gemv --yosys-stat`

Expected: PASS; all 256 observed signed values and raw-byte SHA-256 equal the fixture, and Yosys completes.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_schema_to_calyx.py scripts/pipeline/run_fixed_point_calyx_sv.py tests/test_tinystories_1m_fixed_point_schema_calyx.py
git commit -m "feat: observe full exact GEMV trace in SV"
```

### Task 3: Observe exact requantization independently

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_schema_to_calyx.py`
- Modify: `scripts/pipeline/run_fixed_point_calyx_sv.py`
- Modify: `tests/test_tinystories_1m_fixed_point_schema_calyx.py`

**Interfaces:**

- Consumes: verified accumulator, weight-scale, and output-scale tensors and Task-2 requantization attributes.
- Produces: `generate_requantize_kernel(schema_path: Path, fixture_path: Path) -> CalyxArtifact` and `run_requantize_sv(artifact: CalyxArtifact, fixture_path: Path) -> dict[str, list[int]]` with simulator-observed `codes_i8` and `q16_16`.
- Task 4 reuses this hardware/ABI; it does not use a software replacement.

- [ ] **Step 1: Write the failing requantization test**

```python
def test_generated_sv_observes_exact_requantized_fixture_values(self):
    lowerer = load_lowerer()
    observed = lowerer.run_requantize_sv(lowerer.generate_requantize_kernel(SCHEMA, FIXTURE), FIXTURE)
    fixture = json.loads(FIXTURE.read_text())
    expected = [x for row in fixture["tensors"]["requantized_codes_i8"]["values"] for x in row]
    self.assertEqual(observed["codes_i8"], expected)
```

- [ ] **Step 2: Run the test to show the interface is absent**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_generated_sv_observes_exact_requantized_fixture_values -v`

Expected: FAIL because the generated requantization kernel/runner is absent.

- [ ] **Step 3: Generate fixed-width signed half-up and saturation datapath**

```python
# Generated logic accepts only schema attrs:
# real_q16_16 = signed_magnitude_half_up_shift(acc * weight_scale_q8_24, 16)
# code_i8 = saturate_i8(signed_magnitude_half_up_divide(real_q16_16, output_scale_q8_24))
```

Reject an unknown width, rounding mode, signedness, or saturation policy before
generation; expose result memories to the harness.

- [ ] **Step 4: Verify exact values and reject altered rounding**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_generated_sv_observes_exact_requantized_fixture_values tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_altered_rounding_rule_is_rejected_before_lowering -v`

Expected: PASS; all 256 observed codes equal the fixture and `toward_zero` is rejected before generation.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_schema_to_calyx.py scripts/pipeline/run_fixed_point_calyx_sv.py tests/test_tinystories_1m_fixed_point_schema_calyx.py
git commit -m "feat: observe exact fixed point requantization in SV"
```

### Task 4: Compose the slice and emit an SV acceptance receipt

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_schema_to_calyx.py`
- Modify: `scripts/pipeline/run_fixed_point_calyx_sv.py`
- Modify: `tests/test_tinystories_1m_fixed_point_schema_calyx.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-sv-receipt.json`

**Interfaces:**

- Consumes: Task 2 full-GEMV and Task 3 requantization module/ABI.
- Produces: `run_composed_slice_sv(schema_path: Path, fixture_path: Path) -> dict[str, object]` with `accumulator_trace_sha256`, `requantized_codes_sha256`, `cycles`, generated artifact paths, and `receipt_sha256`.

- [ ] **Step 1: Write the failing composed acceptance test**

```python
def test_generated_sv_composed_slice_matches_all_fixture_checkpoints(self):
    lowerer = load_lowerer()
    receipt = lowerer.run_composed_slice_sv(SCHEMA, FIXTURE)
    fixture = json.loads(FIXTURE.read_text())
    self.assertEqual(receipt["fixture_receipt_sha256"], fixture["receipt_sha256"])
    self.assertEqual(receipt["accumulator_trace_sha256"], fixture["tensors"]["gemv_accumulator_i64"]["sha256"])
    self.assertEqual(receipt["requantized_codes_sha256"], fixture["tensors"]["requantized_codes_i8"]["sha256"])
```

- [ ] **Step 2: Run the test to prove no composed acceptance exists**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx.FixedPointSchemaCalyxTest.test_generated_sv_composed_slice_matches_all_fixture_checkpoints -v`

Expected: FAIL because `run_composed_slice_sv` is absent.

- [ ] **Step 3: Compose generated control and self-hashed receipt**

```python
receipt = {
    "schema": "llm2fpga-fixed-point-gemv-requantize-generated-sv-v1",
    "fixture_receipt_sha256": fixture["receipt_sha256"],
    "schema_receipt_sha256": schema["receipt_sha256"],
    "accumulator_trace_sha256": observed_trace_sha256,
    "requantized_codes_sha256": observed_codes_sha256,
    "cycles": observed_cycles,
}
receipt["receipt_sha256"] = sha256(canonical_json_without_receipt_hash(receipt))
```

Name the generated Futil, SV, and harness paths in the receipt and verify the
self-hash before accepting it.

- [ ] **Step 4: Run all acceptance and regression gates**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_schema_calyx tests.test_fixed_point_schema -v && nix develop -c python scripts/pipeline/run_fixed_point_calyx_sv.py --schema artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-schema.json --fixture artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json --composed --yosys-stat`

Expected: PASS; generated SV matches complete accumulator and code hashes, writes a valid self-hashed receipt, and Yosys completes.

- [ ] **Step 5: Commit and independently review**

```bash
git add scripts/pipeline/lower_fixed_point_schema_to_calyx.py scripts/pipeline/run_fixed_point_calyx_sv.py tests/test_tinystories_1m_fixed_point_schema_calyx.py artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-sv-receipt.json
git commit -m "feat: prove exact fixed point slice in generated SV"
```

## Self-Review

**Spec coverage:** Tasks 1–4 respectively prove memory timing/one MAC, all ordered MACs, exact fixed-point boundary arithmetic, and composition with trace/result receipt. The global constraints cover authority, scope, timing, and fresh quit conditions.

**Placeholder scan:** Every task has named files, interfaces, a concrete failing test, a failure command, an implementation invariant, a passing command, and a commit.

**Type consistency:** Generators accept `Path` schema/fixture inputs and return `CalyxArtifact`; runners return JSON-compatible dictionaries. Task 4 consumes only the runner interfaces established by Tasks 2–3.
