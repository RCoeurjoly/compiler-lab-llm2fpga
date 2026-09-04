# Exact TinyStories Attention Crossing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the exact four-row TinyStories-1M block-0 attention path and its handoff into the proven MLP input boundary in generated Calyx/SV.

**Architecture:** Capture an authenticated four-row attention fixture shared with the MLP fixture. Prove generated-SV `ln_1`, then Q/K/V plus causal attention context, then emit one direct-memory Calyx component for `ln_1 → Q/K/V → attention → out projection → residual → ln_2 → c_fc input Q/DQ` and a self-hashed receipt.

**Tech Stack:** Python through `nix develop`, authenticated exact PyTorch adapter, Calyx 0.7.1, Verilator `--public-flat-rw`, Yosys, unittest.

**Spec:** `docs/superpowers/specs/2026-09-04-exact-tinystories-attention-design.md`

## Global Constraints

- Use exactly prompt `[7454, 2402, 257, 640]`, block 0, four rows, width 64, 16 heads, and head width 4.
- The exact adapter controls all arithmetic: Q16.16/Q8.24, signed-i8 Q/DQ, ascending signed-i64 wrapping GEMV MAC, fixed LayerNorm, exp LUT, and signed attention division.
- Authenticate the new fixture and linked MLP fixture at capture, lowering, and harness-run time. The c_fc input Q/DQ records must equal the MLP fixture bit-for-bit.
- Host code preloads only immutable source inputs, parameter/weight/activation scale memories, and the exp LUT. It may zero but not preload any checkpoint memory or expected-result array.
- Final output has exactly one Calyx `main`; all crossings use generated hardware memories. Use `-d cell-share` only for explicitly staged arithmetic.
- Require a useful artifact or diagnostic inside 30 minutes per complete composition attempt; after two evidence-backed failures, record a schema decision rather than expanding scope.
- Make no full-model, token-generation, board, DDR3, PCIe, RC, generic-SCF, arbitrary-PyTorch, timing, or copied-RTL claim.

---

### Task 1: Authenticated four-row attention fixture

**Files:**

- Create: `TinyStories/capture_fixed_point_attention_crossing_slice.py`
- Create: `tests/test_tinystories_1m_fixed_point_attention_crossing.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json`

**Interfaces:** Produces `capture() -> dict[str, Any]`, `verify_fixture(path: Path) -> dict[str, Any]`, and `verify_fixed_point_replay(path: Path) -> None`. Later lowerers consume the returned fixture and linked MLP authority.

- [ ] **Step 1: Write the failing fixture/link test**

```python
def test_attention_fixture_replays_and_links_mlp_input(self):
    attention = capture_attention.verify_fixture(ATTENTION_FIXTURE)
    capture_attention.verify_fixed_point_replay(ATTENTION_FIXTURE)
    mlp = capture_mlp.verify_fixture(MLP_FIXTURE)
    for name in ("c_fc_input_codes_i8", "c_fc_input_scale_q8_24", "c_fc_input_q16_16"):
        self.assertEqual(attention["linked_mlp"][name]["little_endian_int64_sha256"],
                         mlp["tensors"][name]["little_endian_int64_sha256"])
```

- [ ] **Step 2: Run RED**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_attention_crossing -v`

Expected: FAIL because the capture module and fixture do not exist.

- [ ] **Step 3: Capture complete exact observations**

Authenticate `load_successor_exact_model`, assert block-0 QDQ indices `0:24`, GEMV accumulators `0:4`, and nonlinear indices `0:3`, then rerun the adapter's exact integer attention calculation with observations for all rows, heads, and causal positions. Capture source input, ln1/ln2 parameters and values, Q/K/V and out-projection QDQ/accumulator/post-rescale records, score/max/delta/exp/denominator/numerator/context, residual, ln2, and c_fc input QDQ. Record raw LE signed-i64 hashes, shapes, semantic labels, immutable source tensors, adapter/package identity, and an outer self-hash. Reject any mismatch against the MLP fixture's three c_fc input records.

- [ ] **Step 4: Run GREEN**

Run:

```bash
nix develop -c python TinyStories/capture_fixed_point_attention_crossing_slice.py \
  --output artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json --verify
nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_attention_crossing \
  -v
```

Expected: eager authenticated capture, integer replay, per-record hashes, and the MLP link all pass.

- [ ] **Step 5: Commit**

```bash
git add TinyStories/capture_fixed_point_attention_crossing_slice.py \
  tests/test_tinystories_1m_fixed_point_attention_crossing.py \
  artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json
git commit -m "feat: capture exact fixed point attention crossing fixture"
```

### Task 2: Exact generated-SV `ln_1` diagnostic gate

**Files:**

- Create: `scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py`
- Modify: `tests/test_tinystories_1m_fixed_point_attention_crossing.py`

**Interfaces:** Produces `generate_ln1_kernel(fixture_path: Path) -> CalyxArtifact` and `run_ln1_sv(artifact: CalyxArtifact, fixture_path: Path) -> dict[str, object]`. Task 3 consumes its fixed LayerNorm primitives and source-memory contract.

- [ ] **Step 1: Write the failing LayerNorm SV test**

```python
def test_generated_sv_observes_exact_ln1(self):
    artifact = lowerer.generate_ln1_kernel(ATTENTION_FIXTURE)
    observed = lowerer.run_ln1_sv(artifact, ATTENTION_FIXTURE)
    self.assertEqual(observed["ln1_q16_16"], tensor_values("ln1_output_q16_16"))
```

- [ ] **Step 2: Run RED**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_attention_crossing.AttentionCrossingTest.test_generated_sv_observes_exact_ln1 -v`

Expected: FAIL because the lowerer and runner do not exist.

- [ ] **Step 3: Implement fixed LayerNorm hardware**

Emit generated memory/control for each of four 64-wide rows: signed truncating mean, delta square accumulation, `+42950`, restoring integer square root, signed truncating normalization, Q16.16 gamma multiplication and beta addition. Preload only block input and `ln1` gamma/beta; read the hardware-owned ln1 memory after `done`. Revalidate fixture authority at generation and run time; bind the artifact to the emitted Futil and compile with only any necessary scoped `-d cell-share` disablement.

- [ ] **Step 4: Run GREEN**

Run the focused test above.

Expected: all 256 generated-SV ln1 values and raw-byte hash equal the fixture, with no expected-result preload array.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py \
  tests/test_tinystories_1m_fixed_point_attention_crossing.py
git commit -m "feat: observe exact fixed layer norm in SV"
```

### Task 3: Exact generated-SV Q/K/V causal-attention diagnostic gate

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py`
- Modify: `tests/test_tinystories_1m_fixed_point_attention_crossing.py`

**Interfaces:** Produces `generate_causal_attention_kernel(fixture_path: Path) -> CalyxArtifact` and `run_causal_attention_sv(artifact: CalyxArtifact, fixture_path: Path) -> dict[str, object]`. Task 4 consumes the direct-memory Q/K/V/context phases.

- [ ] **Step 1: Write the failing causal-attention test**

```python
def test_generated_sv_observes_exact_qkv_and_causal_context(self):
    artifact = lowerer.generate_causal_attention_kernel(ATTENTION_FIXTURE)
    observed = lowerer.run_causal_attention_sv(artifact, ATTENTION_FIXTURE)
    for name in ("q_output_q16_16", "k_output_q16_16", "v_output_q16_16", "attention_context_q16_16"):
        self.assertEqual(observed[name], tensor_values(name))
```

- [ ] **Step 2: Run RED**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_attention_crossing.AttentionCrossingTest.test_generated_sv_observes_exact_qkv_and_causal_context -v`

Expected: FAIL because the causal generator and runner do not exist.

- [ ] **Step 3: Implement Q/K/V and causal context hardware**

Emit one generated component which first computes hardware-owned `ln1_q16_16` from block input and ln1 parameters, then consumes it with Q/K/V source parameters/scales and the exp LUT; performs each 64-by-64 exact GEMV/QDQ; writes Q/K/V memories; then computes every causal `[row, head, key<=row]` score/max/delta/exp/denominator/numerator/context record. Use the exact signed division correction from the fixture adapter. The harness may not preload ln1, Q/K/V, score, probability, or context results. Require a checkpoint comparison of all captured causal tensors, not merely final context.

- [ ] **Step 4: Run GREEN**

Run the focused test above.

Expected: every Q/K/V and causal tensor hash equals the fixture; all intermediate memories are hardware-written and host-zeroed only.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py \
  tests/test_tinystories_1m_fixed_point_attention_crossing.py
git commit -m "feat: observe exact causal attention in SV"
```

### Task 4: One-component attention-to-MLP-boundary receipt

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py`
- Create: `scripts/pipeline/run_fixed_point_attention_crossing_sv.py`
- Modify: `tests/test_tinystories_1m_fixed_point_attention_crossing.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-attention-crossing-sv-receipt.json`

**Interfaces:** Produces `run_composed_attention_sv(fixture_path: Path, mlp_fixture_path: Path) -> dict[str, object]` and a canonical receipt. It is the authoritative attention-to-MLP handoff artifact.

- [ ] **Step 1: Write the failing full-composition test**

```python
def test_one_generated_sv_main_matches_attention_and_mlp_boundary(self):
    receipt = lowerer.run_composed_attention_sv(ATTENTION_FIXTURE, MLP_FIXTURE)
    self.assertEqual(receipt["execution"]["component_count"], 1)
    self.assertEqual(receipt["observed"]["ln2_q16_16_sha256"], tensor_hash("ln2_output_q16_16"))
    self.assertEqual(receipt["observed"]["c_fc_input_q16_16_sha256"],
                     mlp_tensor_hash("c_fc_input_q16_16"))
```

- [ ] **Step 2: Run RED**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_attention_crossing.AttentionCrossingTest.test_one_generated_sv_main_matches_attention_and_mlp_boundary -v`

Expected: FAIL because the composed runner is absent.

- [ ] **Step 3: Generate final direct-memory component and receipt**

Emit exactly one Calyx `main`: ln1; Q/K/V QDQ and GEMVs; causal attention; out-projection QDQ/GEMV; residual; ln2; c_fc input QDQ. Preserve each checkpoint memory as hardware-owned and read every value post-run. Assert in code that Futil contains one `component main`, source-only harness arrays, no expected arrays, and direct generated reads from ln2 into c_fc input QDQ. Build a receipt only after all fixture and linked-MLP hashes compare equal; bind its schema, fixture receipts, input identities, observed hashes, cycle count, Futil/SV/synthesis-SV/harness hashes, and canonical self-hash.

- [ ] **Step 4: Run all acceptance gates**

Run:

```bash
nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_attention_crossing -v
nix develop -c python scripts/pipeline/run_fixed_point_attention_crossing_sv.py \
  --fixture artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json \
  --mlp-fixture artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json \
  --composed --yosys-stat
```

Expected: one `main`; every captured attention checkpoint and c_fc input Q/DQ matches; receipt self-hash and linked MLP authority validate; same-Futil Yosys stat succeeds.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_attention_crossing_to_calyx.py \
  scripts/pipeline/run_fixed_point_attention_crossing_sv.py \
  tests/test_tinystories_1m_fixed_point_attention_crossing.py \
  artifacts/reference/tinystories-1m-fixed-point-attention-crossing-sv-receipt.json
git commit -m "feat: prove exact attention crossing in generated SV"
```

## Self-Review

- Spec coverage: Task 1 establishes exact four-row and MLP-linked authority; Tasks 2 and 3 provide the required ln1/context diagnostic gates; Task 4 proves the whole one-main direct-memory path, receipt, and same-Futil synthesis.
- Placeholder scan: no deferred behavior, unnamed interface, or generic test instruction remains.
- Interface consistency: Task 1 names the fixture verifier, Tasks 2/3 name their diagnostic producers, and Task 4 consumes the named attention and MLP fixtures through `run_composed_attention_sv`.
