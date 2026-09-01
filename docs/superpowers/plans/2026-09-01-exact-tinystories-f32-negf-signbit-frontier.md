# Exact TinyStories F32 NegF Sign-Bit Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the exact 1,369 prepared TinyStories-1M `arith.negf : f32` blockers with an IEEE-exact sign-bit XOR legalization, then authenticate and measure the successor pre-Calyx frontier without invoking the full-model Calyx route.

**Architecture:** Add a scalar-f32-only MLIR pass that lowers `negf` to equal-width bitcasts and XOR with `0x80000000`, preserving all binary32 encodings including signed zero and NaN payloads. Wire it into the shared and exact pre-Calyx preparation sequences after exact-math legalization, rotate only measured authority identities, and independently replay the exact registered stage to classify the successor.

**Tech Stack:** C++ MLIR pass plugin, MLIR 21.1.2, CIRCT, Python `unittest`, Nix flakes, canonical hash-bound receipts.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve immutable c22 input SHA-256 `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6` and normalized flat-SCF SHA-256 `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`.
- Preserve the current exact model, tokenizer, quantization, PyTorch export, Torch-MLIR, Linalg/SCF, and static-memref normalization contracts.
- Lower only scalar f32 `arith.negf`. Leave f64, vector/tensor, and all non-negf operations unchanged.
- Implement IEEE negation as `bitcast f32→i32`, XOR `0x80000000`, `bitcast i32→f32`. Do not use `0.0 - x`, multiplication by `-1.0`, or plain i64 negation.
- Preserve `fastmath<none>` semantics, signed zero, infinities, subnormals, and every NaN encoding bit except the toggled sign bit.
- A bounded fixture-only CIRCT structural probe is allowed. Full-model Calyx, SV, synthesis, and board work remain forbidden in this plan.
- Use test-first development and commit every verified task.

---

### Task 1: Implement and Prove Scalar F32 NegF Legalization

**Files:**
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`
- Modify: `tests/test_calyx_math_legalization.py`
- Create: `reproducers/calyx-math-negf/f32-signbit.mlir`
- Create: `scripts/pipeline/verify_f32_negf_signbit_semantics.py`
- Create: `tests/test_f32_negf_signbit_semantics.py`
- Create: `docs/results/2026-09-01-exact-tinystories-f32-negf-signbit-contract.md`

**Interfaces:**
- Consumes: scalar `arith::NegFOp` with f32 input/result.
- Produces: `arith.bitcast f32 to i32`, `arith.xori` with sign mask `-2147483648 : i32` (bit pattern `0x80000000`), and `arith.bitcast i32 to f32`.

- [ ] **Step 1: Write semantic and boundary REDs**

Add an independent bit-pattern oracle:

```python
def expected_negf_bits(bits: int) -> int:
    return bits ^ 0x80000000
```

Test positive/negative zero, normals, subnormals, infinities, multiple quiet/signaling NaN payloads, and deterministic random 32-bit patterns. The plugin fixture must contain matching scalar f32 negf plus nonmatching scalar f64 and vector f32 negf. Require nonmatches to remain.

- [ ] **Step 2: Run REDs**

```bash
nix develop -c python -m unittest \
  tests/test_f32_negf_signbit_semantics.py \
  tests/test_calyx_math_legalization.py -v
```

Expected: the independent oracle passes, while the plugin has no registered negf legalization and the matching fixture remains illegal to CIRCT.

- [ ] **Step 3: Implement and register the pass**

Add `LowerNegFForCalyxPass` with argument `llm2fpga-lower-negf-for-calyx`. Collect matching ops before rewriting, register Arith, and replace only scalar f32 negf with:

```mlir
%bits = arith.bitcast %x : f32 to i32
%mask = arith.constant -2147483648 : i32
%flipped = arith.xori %bits, %mask : i32
%result = arith.bitcast %flipped : i32 to f32
```

Register the pass type ID and plugin entry alongside the existing exact-math passes. Preserve locations on all created operations.

- [ ] **Step 4: Prove transformed structure and bounded CIRCT acceptance**

Run the pass on the fixture. Require matching f32 negf to disappear, both bitcasts and one xori/sign mask to appear, and f64/vector nonmatches to remain. Lower only the matching memory-backed function with:

```bash
circt-opt lowered.mlir --lower-scf-to-calyx='top-level-function=main'
```

Require nonempty Calyx IR containing `calyx.std_xor`, no `arith.negf`, and no floating add/sub primitive or added floating register/control group.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python -m unittest \
  tests/test_f32_negf_signbit_semantics.py \
  tests/test_calyx_math_legalization.py -v
nix build .#llm2fpgaMlirPasses -L
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add tools/mlir-passes/FoldConstantTruncFOps.cpp \
  reproducers/calyx-math-negf/f32-signbit.mlir \
  scripts/pipeline/verify_f32_negf_signbit_semantics.py \
  tests/test_f32_negf_signbit_semantics.py \
  tests/test_calyx_math_legalization.py \
  docs/results/2026-09-01-exact-tinystories-f32-negf-signbit-contract.md
git commit -m "feat: lower f32 negf for Calyx"
```

Record the resolved plugin output path and measured SHA-256 in the result document.

### Task 2: Wire, Authenticate, and Measure the NegF Successor

**Files:**
- Modify: `nix/pipeline.nix`
- Modify: `nix/exact-tinystories-normalized.nix`
- Modify: `flake.nix`
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py`
- Modify: `tests/test_tinystories_1m_exact_normalized_registration.py`
- Modify: `docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md`
- Create: `docs/results/2026-09-01-exact-tinystories-f32-negf-successor.md`

**Interfaces:**
- Consumes: Task 1's reviewed pass plugin and the authenticated floor-successor registered package.
- Produces: shared/exact preparation pipelines containing `llm2fpga-lower-negf-for-calyx` immediately after `llm2fpga-lower-exact-math-for-calyx`, plus a newly hash-bound exact prepared artifact and successor receipt.

- [ ] **Step 1: Write pipeline/authority/frontier REDs**

Require the shared and exact preparation literals to contain exactly one negf pass after exact-math and before i1-uitofp. Require the stale plugin hash to fail after Task 1, independent replay to produce `arith.negf: 0`, normalized SHA to remain `e669a263...d77`, and all commands to remain pre-Calyx only. Add mutation coverage for omitted/duplicated/reordered negf pass and stale plugin/prepared hashes.

- [ ] **Step 2: Run REDs**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py \
  tests/test_calyx_math_legalization.py -v
```

Expected: stale pipeline/plugin authority fails and the registered preparation still reports 1,369 negf operations.

- [ ] **Step 3: Wire the pass and rotate measured authority**

Insert the pass in `nix/pipeline.nix` and `nix/exact-tinystories-normalized.nix`. Audit any exact hard-coded preparation literal in `flake.nix`; update it only if it represents the same pre-Calyx contract. Build Task 1's reviewed plugin, measure its SHA-256, and update only the plugin/pipeline authority constants in `flake.nix`, verifier, and tests. Do not change c22, normalized, parser, checker, model, or normalization identities.

- [ ] **Step 4: Rebuild, independently replay, and classify**

```bash
nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L
nix develop -c python \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py -v
```

Require `arith.negf: 0` and `math.floor: 0`. Measure all remaining prohibited counts and original-text first locations. `math.absi` was previously 1,156 at 855:16, but its post-rewrite count/location must be measured. If any negf remains, stop on the first nonmatching signature. Otherwise authorize only a later plan for the earliest measured successor. Keep `calyx_authorized: false` while any residual or diagnostic remains.

- [ ] **Step 5: Record identities, verify scope, and commit**

Record plugin, prepared, legality-file, receipt-self, and manifest SHA-256 values. Verify the exact package command closure contains no full-model CIRCT/Calyx/SV/synthesis/board action.

```bash
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add nix/pipeline.nix nix/exact-tinystories-normalized.nix flake.nix \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py \
  tests/test_tinystories_1m_exact_normalized_registration.py \
  docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md \
  docs/results/2026-09-01-exact-tinystories-f32-negf-successor.md
git commit -m "feat: register exact f32 negf successor"
```

## Follow-Up Rule

- If negf remains, target only its first measured nonmatching signature.
- If negf is zero and another prohibited operation remains, target only the earliest measured successor and its semantic context.
- Only an authenticated clean prepared receipt may authorize a separate full-model Calyx plan; this plan never runs that route.
