# Exact TinyStories Block Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove one complete exact TinyStories-1M block-0 four-row path in generated Calyx/SV, ending at the final block residual.

**Architecture:** A compact composition fixture links the previously authenticated attention and MLP fixtures and adds only `block_output_q16_16[4,64]`. A new compiler-owned block lowerer emits one Calyx main that owns every attention-to-MLP and final-residual crossing; a final runner produces a self-hashed receipt and same-Futil synthesis evidence.

**Tech Stack:** Python through `nix develop`, exact fixed-point TinyStories adapter and fixtures, Calyx 0.7.1, Verilator `--public-flat-rw`, Yosys, unittest.

**Spec:** `docs/superpowers/specs/2026-09-04-exact-tinystories-block-composition-design.md`

## Global Constraints

- Use only authenticated prompt `[7454, 2402, 257, 640]`, block 0, four rows, width 64, and the exact fixed-point arithmetic selected by `_ExactFixedPointModel`.
- Link and authenticate the existing attention and MLP fixtures before consuming any record; add only the derived/captured `block_output_q16_16[4,64]` fixture record.
- Preserve Q16.16/Q8.24, signed-int8 Q/DQ, ascending signed-i64 wrapping MAC, fixed LayerNorm, exact causal exp-LUT/division, fixed GELU LUT, signed-magnitude half-up rescale, and residual additions.
- Generate exactly one Calyx `main`; `ln_2 → c_fc` and `attention_residual + c_proj_output → block_output` are direct generated-memory handoffs.
- The harness preloads only immutable input, parameters, codes, scales, and LUTs; it may zero but never preload expected outputs or computed attention/MLP/block values.
- Both simulation and synthesis consume the same Futil. Disable `cell-share` only if the existing reproducible generated-Calyx cycle diagnostic remains applicable.
- A full attempt must emit an artifact or useful first-mismatch diagnostic within 30 minutes. Stop after two evidence-backed failures; do not expand to top-level forward/decode or reference RTL.
- Make no full-model, token, board, DDR3, PCIe, RC, generic-SCF, arbitrary-PyTorch, timing, throughput, latency, or copied-RTL claim.

---

### Task 1: Linked complete-block fixture

**Files:**

- Create: `TinyStories/capture_fixed_point_block_composition_slice.py`
- Create: `tests/test_tinystories_1m_fixed_point_block_composition.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json`

**Interfaces:** Produces `capture() -> dict[str, Any]`, `verify_fixture(path: Path) -> dict[str, Any]`, and `verify_block_output_replay(path: Path) -> None`. Later tasks consume the verified fixture with its linked attention and MLP authority.

- [ ] **Step 1: Write the failing linked-fixture test**

```python
def test_block_fixture_links_both_slices_and_replays_final_residual(self):
    fixture = capture_block.verify_fixture(BLOCK_FIXTURE)
    capture_block.verify_block_output_replay(BLOCK_FIXTURE)
    self.assertEqual(fixture["slice"], {"block": 0, "rows": 4, "width": 64})
    self.assertEqual(fixture["tensors"]["block_output_q16_16"]["shape"], [4, 64])
    self.assertEqual(fixture["linked_attention"]["receipt_sha256"], attention_receipt())
    self.assertEqual(fixture["linked_mlp"]["receipt_sha256"], mlp_receipt())
```

- [ ] **Step 2: Run RED**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_block_composition -v`

Expected: FAIL because the block fixture capture module and fixture do not exist.

- [ ] **Step 3: Capture and authenticate the new residual contract**

Load `capture_fixed_point_attention_crossing_slice.verify_fixture` and
`capture_fixed_point_mlp_crossing_slice.verify_fixture`; reject any fixture
identity, receipt, tensor-binding, shape, or source-prompt discrepancy.
Compute `block_output_q16_16` by signed Q16.16 integer addition of the linked
`attention_residual_q16_16[4,64]` and `c_proj_output_q16_16[4,64]` records.
Record only that new tensor, its semantic name, shape, canonical hash, raw
little-endian signed-i64 hash, byte length, the complete linked fixture
authority, and canonical outer self-hash. Replay must independently recompute
the residual and reject a resealed linked-record mutation.

- [ ] **Step 4: Run GREEN**

Run:

```bash
nix develop -c python TinyStories/capture_fixed_point_block_composition_slice.py \
  --output artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json --verify
nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_block_composition -v
```

Expected: linked attention/MLP fixture authentication, four-row residual
replay, outer self-hash, and mutation rejection all pass.

- [ ] **Step 5: Commit**

```bash
git add TinyStories/capture_fixed_point_block_composition_slice.py \
  tests/test_tinystories_1m_fixed_point_block_composition.py \
  artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json
git commit -m "feat: capture exact complete block fixture"
```

### Task 2: One-main generated complete block observation

**Files:**

- Create: `scripts/pipeline/lower_fixed_point_block_composition_to_calyx.py`
- Modify: `tests/test_tinystories_1m_fixed_point_block_composition.py`

**Interfaces:** Produces `generate_block_kernel(block_fixture: Path, attention_fixture: Path, mlp_fixture: Path) -> CalyxArtifact` and `run_block_sv(artifact: CalyxArtifact, block_fixture: Path, attention_fixture: Path, mlp_fixture: Path) -> dict[str, object]`. Task 3 consumes all observed hashes and generated artifact paths.

- [ ] **Step 1: Write the failing complete-block SV test**

```python
def test_one_generated_main_observes_exact_complete_block(self):
    artifact = lowerer.generate_block_kernel(BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE)
    observed = lowerer.run_block_sv(artifact, BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE)
    self.assertEqual(observed["component_count"], 1)
    self.assertEqual(observed["block_output_q16_16"], block_tensor("block_output_q16_16"))
    self.assertEqual(observed["c_fc_input_q16_16"], mlp_tensor("c_fc_input_q16_16"))
```

- [ ] **Step 2: Run RED**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_block_composition.BlockCompositionTest.test_one_generated_main_observes_exact_complete_block -v`

Expected: FAIL because the complete-block lowerer and runner do not exist.

- [ ] **Step 3: Emit and execute direct complete-block hardware**

Authenticate all three fixtures before generation and at run time. Emit a
single Calyx `main` that owns the complete attention phases already proven by
the attention lowerer, directly carries hardware `ln_2` into c_fc input Q/DQ,
executes the exact c_fc/GELU/c_proj phases already proven by the MLP lowerer,
and reads hardware-owned attention residual and c_proj output for the final
signed Q16.16 addition. Preserve every observable attention and MLP memory
plus `block_output_q16_16`. Assert one main; source-only preload arrays; no
expected arrays; zero-only host initialization of all computed memories; direct
`ln_2 → c_fc` and `attention_residual + c_proj_output → block_output` reads.
Compare every post-run hardware checkpoint with the linked fixtures and block
fixture; report the first named mismatch.

- [ ] **Step 4: Run GREEN**

Run the focused test above.

Expected: every linked attention and MLP checkpoint plus all 256 final block
output words match exactly in one generated-SV execution. The result reports
component count, cycle count, all observed hashes, and directness evidence.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_block_composition_to_calyx.py \
  tests/test_tinystories_1m_fixed_point_block_composition.py
git commit -m "feat: observe exact complete block in generated SV"
```

### Task 3: Complete-block receipt and same-Futil acceptance

**Files:**

- Modify: `scripts/pipeline/lower_fixed_point_block_composition_to_calyx.py`
- Create: `scripts/pipeline/run_fixed_point_block_composition_sv.py`
- Modify: `tests/test_tinystories_1m_fixed_point_block_composition.py`
- Create: `artifacts/reference/tinystories-1m-fixed-point-block-composition-sv-receipt.json`

**Interfaces:** Produces `run_composed_block_sv(block_fixture: Path, attention_fixture: Path, mlp_fixture: Path) -> dict[str, object]` and a canonical self-hashed acceptance receipt.

- [ ] **Step 1: Write the failing receipt/CLI test**

```python
def test_complete_block_receipt_binds_all_linked_authority(self):
    receipt = lowerer.run_composed_block_sv(BLOCK_FIXTURE, ATTENTION_FIXTURE, MLP_FIXTURE)
    self.assertEqual(receipt["execution"]["component_count"], 1)
    self.assertFalse(receipt["execution"]["host_intermediate"])
    self.assertEqual(receipt["observed"]["block_output_q16_16_sha256"], block_tensor_hash())
    self.assertEqual(receipt["linked_fixtures"]["mlp_c_fc_input_q16_16_sha256"], mlp_tensor_hash("c_fc_input_q16_16"))
```

- [ ] **Step 2: Run RED**

Run: `nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_block_composition.BlockCompositionTest.test_complete_block_receipt_binds_all_linked_authority -v`

Expected: FAIL because `run_composed_block_sv` and the committed receipt are absent.

- [ ] **Step 3: Serialize and validate canonical receipt**

Require all observed hashes to match before emitting a receipt. Bind all three
fixture receipts and tensor-bindings, one main, source/computed memory
partition, direct handoff declarations, cycle count, every attention/MLP/block
output hash, Futil/simulation-SV/synthesis-SV/harness hashes, compiler
arguments, and canonical self-hash. Compile synthesis SV from the identical
Futil. Add a CLI accepting `--block-fixture`, `--attention-fixture`,
`--mlp-fixture`, `--composed`, and `--yosys-stat`; it must regenerate/validate
the committed receipt and reject fixture or receipt tampering.

- [ ] **Step 4: Run all acceptance gates**

Run:

```bash
nix develop -c python -m unittest tests.test_tinystories_1m_fixed_point_block_composition -v
nix develop -c python scripts/pipeline/run_fixed_point_block_composition_sv.py \
  --block-fixture artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json \
  --attention-fixture artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json \
  --mlp-fixture artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json \
  --composed --yosys-stat
```

Expected: all linked checkpoints and block output match; receipt self-hash and
three fixture authorities validate; exactly one main and source-only host
preload are enforced; same-Futil Yosys stat succeeds.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/lower_fixed_point_block_composition_to_calyx.py \
  scripts/pipeline/run_fixed_point_block_composition_sv.py \
  tests/test_tinystories_1m_fixed_point_block_composition.py \
  artifacts/reference/tinystories-1m-fixed-point-block-composition-sv-receipt.json
git commit -m "feat: prove exact complete block in generated SV"
```

## Self-Review

- Spec coverage: Task 1 supplies the new linked output contract; Task 2 proves one-main direct complete-block behavior; Task 3 proves receipt, tamper rejection, and same-Futil synthesis.
- Placeholder scan: every task names files, produced interfaces, tests, commands, and commit scope; no deferred behavior is left unnamed.
- Interface consistency: Tasks 2 and 3 use the same three fixture arguments and block-lowerer naming; Task 3 packages the Task 2 observed hashes rather than recalculating a host result.
