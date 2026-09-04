# Exact TinyStories F64 Floor-to-I64 Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the exact 1,376 prepared TinyStories-1M `math.floor : f64` blockers by lowering only the observed `arith.fptosi(math.floor(x)) : f64 -> i64` pair, then authenticate and measure the successor pre-Calyx frontier without invoking Calyx.

**Architecture:** Extend the existing `llm2fpga-lower-exact-math-for-calyx` pass with a fused rewrite whose result is already integer, preserving the existing binary64 division and avoiding an unjustified integer-division substitution or broad standalone-f64-floor contract. Prove the rewrite against an independent defined-domain IEEE-754 host oracle and structural CIRCT probe, then rotate the reviewed plugin identity in the registered Nix stage and independently replay the exact preparation to classify only the next blocker.

**Tech Stack:** C++ MLIR pass plugin, MLIR 21.1.2, CIRCT, Python `unittest`, Nix flakes, canonical hash-bound receipts.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve model `roneneldan/TinyStories-1M` revision `ac533fb8b4f69c71894bf96badfe11e6294d9fcf`, the frozen kev-gpt package/tokenizer/quantization contract, and the existing exact PyTorch-to-flat-SCF route.
- Preserve immutable c22 input SHA-256 `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6` and normalized flat-SCF SHA-256 `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`.
- Target only `math.floor : f64` whose sole user is `arith.fptosi : f64 to i64`; do not widen standalone f64 floor, ceil, rsqrt, or another math operation.
- Retain the original f64 producer, including `arith.divf`; do not replace the chain with integer division because binary64 conversion/division precision and exceptional behavior are not proven equivalent over all reachable i64 values.
- The equivalence contract covers executions where the original final `arith.fptosi` is defined: finite input whose floored value is representable as signed i64. NaN, infinities, and out-of-range conversions are outside that original defined domain and must not be assigned a new claimed semantic result.
- Do not change PCIe, DDR3, board integration, model inputs, or quantization.
- This plan stops at authenticated pre-Calyx successor classification. Do not invoke the full-model Calyx route, SV export, synthesis, or board tools.
- Use test-first development and commit every verified task.

---

### Task 1: Implement and Prove the Fused F64 Floor-to-I64 Rewrite

**Files:**
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`
- Modify: `tests/test_calyx_math_legalization.py`
- Create: `reproducers/calyx-math-floor/f64-floor-to-i64.mlir`
- Create: `scripts/pipeline/verify_f64_floor_to_i64_semantics.py`
- Create: `tests/test_f64_floor_to_i64_semantics.py`
- Create: `docs/results/2026-09-01-exact-tinystories-f64-floor-to-i64-contract.md`

**Interfaces:**
- Consumes: scalar `math::FloorOp` with f64 result and exactly one `arith::FPToSIOp` user producing i64.
- Produces: the original fptosi result replaced by `fptosi(x)`, `sitofp`, ordered-less-than comparison, `select(-1, 0)`, and `addi`; both the floor and its consumer are erased.

- [ ] **Step 1: Write semantic and match-boundary REDs**

Add fixtures/tests that require the observed pair to disappear while these nonmatching cases remain byte-structurally present: standalone f64 floor, f64 floor with two users, f64 floor consumed by fptosi-to-i32, f32 floor-to-i32, and f64 ceil/rsqrt. The positive fixture must use a memory-backed `@main`, not only bare float arguments, and contain positive fraction, negative fraction, positive/negative integer, and negative-zero paths.

The independent Python oracle must compute, for a supplied binary64 `x` in the defined domain:

```python
trunc = math.trunc(x)
lowered = trunc - 1 if x < float(trunc) else trunc
expected = math.floor(x)
assert lowered == expected
```

Exercise exact integers, adjacent representable values via `math.nextafter`, positive and negative fractions, signed zero, values around `2**52` and `2**53`, and representable near-i64-boundary values. Explicitly classify NaN, infinities, and out-of-i64-range floors as outside the original defined domain.

- [ ] **Step 2: Run REDs**

```bash
nix develop -c python -m unittest \
  tests/test_f64_floor_to_i64_semantics.py \
  tests/test_calyx_math_legalization.py -v
```

Expected: semantic host-oracle tests pass independently, while the plugin fixture still contains the positive f64 `math.floor` because the pass accepts only f32.

- [ ] **Step 3: Add the exact fused rewrite**

In `LowerExactMathForCalyxPass`, collect/rewrite the matching floor and consumer before the existing f32 branch. Require f64 floor result, one use, `arith::FPToSIOp`, and i64 result. Emit:

```mlir
%trunc = arith.fptosi %x : f64 to i64
%trunc_f = arith.sitofp %trunc : i64 to f64
%below = arith.cmpf olt, %x, %trunc_f : f64
%delta = arith.select %below, %c-1_i64, %c0_i64 : i64
%rounded = arith.addi %trunc, %delta : i64
```

Replace the consumer with `%rounded`, erase the now-dead floor, and leave every nonmatching operation unchanged. Do not clone or reconstruct a standalone f64 floor result.

- [ ] **Step 4: Prove plugin semantics and structural backend acceptance**

Run the reviewed plugin on the fixture and require the positive pair to contain no `math.floor`, to contain the exact f64/i64 conversion/compare/select/add classes, and to preserve all nonmatching cases. Run the memory-backed positive result through:

```bash
circt-opt lowered.mlir --lower-scf-to-calyx='top-level-function=main'
```

Require nonempty Calyx IR containing `calyx.ieee754.fpToInt`, `calyx.ieee754.intToFp`, and `calyx.ieee754.compare`. This is a bounded structural probe only; it does not authorize the full model or downstream SV.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python -m unittest \
  tests/test_f64_floor_to_i64_semantics.py \
  tests/test_calyx_math_legalization.py -v
nix build .#mlir-passes -L
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add tools/mlir-passes/FoldConstantTruncFOps.cpp \
  reproducers/calyx-math-floor/f64-floor-to-i64.mlir \
  scripts/pipeline/verify_f64_floor_to_i64_semantics.py \
  tests/test_f64_floor_to_i64_semantics.py \
  tests/test_calyx_math_legalization.py \
  docs/results/2026-09-01-exact-tinystories-f64-floor-to-i64-contract.md
git commit -m "feat: lower exact f64 floor to i64"
```

Use the actual exposed pass-plugin package attribute if `mlir-passes` has a different flake spelling; record the resolved attribute and plugin SHA-256 in the result document.

### Task 2: Rotate Plugin Authority and Authenticate the Successor Frontier

**Files:**
- Modify: `flake.nix`
- Modify: `tests/test_tinystories_1m_exact_normalized_registration.py`
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py`
- Modify: `docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md`
- Create: `docs/results/2026-09-01-exact-tinystories-f64-floor-successor.md`

**Interfaces:**
- Consumes: Task 1's reviewed plugin and the registered normalized package authority.
- Produces: a newly hash-bound `pre-calyx.mlir`, legality receipt, manifest, and independently verified successor-frontier classification.

- [ ] **Step 1: Write authority/frontier REDs**

Require the registered package and independent verifier to reject the old plugin hash after the plugin changes. Add exact assertions that independent preparation replay produces zero `math.floor`, preserves normalized input SHA-256 `e669a263...d77`, and leaves `calyx_authorized: false` unless every prohibited/diagnostic count is zero. Assert the next receipt is derived from the replayed prepared bytes and that no command crosses the pre-Calyx boundary.

- [ ] **Step 2: Run REDs**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py -v
```

Expected: the exact package fails its old `79c0ab...d738` plugin identity or still reports 1,376 floors until the authority pin is deliberately rotated.

- [ ] **Step 3: Rotate only measured identities**

Build the reviewed plugin, compute its actual SHA-256, update `expectedPluginSha256` and the verifier/test constant to that measured value, then rebuild the exact package. Do not change c22, normalized, parser, checker, model, or preparation-pipeline identities. Record the new prepared artifact SHA-256, legality file SHA-256, receipt self-hash, and manifest SHA-256 from the built output rather than predicting them.

- [ ] **Step 4: Independently replay and classify**

```bash
nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L
nix develop -c python \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py -v
```

Require all 1,376 `math.floor` sites to be absent. Measure every remaining prohibited class and its first original-text location with schema-v3. Expected carried candidates are `arith.negf` (previously 1,369) and `math.absi` (previously 1,156), but their post-rewrite counts/locations must be measured, not copied. If any `math.floor` remains, stop and report the exact nonmatching signature as the causal frontier. If floor is zero, authorize only a later plan for the earliest measured successor; do not lower it here.

- [ ] **Step 5: Verify no scope crossing and commit**

```bash
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add flake.nix \
  tests/test_tinystories_1m_exact_normalized_registration.py \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py \
  docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md \
  docs/results/2026-09-01-exact-tinystories-f64-floor-successor.md
git commit -m "feat: register exact f64 floor successor"
```

## Follow-Up Rule

- If `math.floor` is nonzero, the next plan targets only the first measured nonmatching floor signature.
- If `math.floor` is zero and another prohibited class remains, the next plan targets only the earliest measured successor operation and its exact semantic context.
- Only a fully clean, authenticated prepared receipt may authorize a separate full-model Calyx-lowering plan. This plan itself never invokes that route.
