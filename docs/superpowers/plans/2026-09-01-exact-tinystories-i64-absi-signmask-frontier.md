# Exact TinyStories I64 AbsI Sign-Mask Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all 1,156 authenticated `math.absi : i64` blockers with exact unflagged modular arithmetic, then authenticate whether the complete prepared TinyStories-1M artifact is clean enough to authorize a separate Calyx plan.

**Architecture:** Extend the existing exact-math pass only for scalar i64 `math.absi`, using arithmetic sign replication, XOR, and unflagged subtraction. Rebuild the reviewed plugin, rotate its measured hash in the exact registered stage, independently replay preparation, and stop at either the first residual or a clean pre-Calyx receipt; this plan itself does not invoke full-model Calyx.

**Tech Stack:** C++ MLIR pass plugin, MLIR 21.1.2, CIRCT, Python `unittest`, Nix flakes, canonical hash-bound receipts.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- Preserve immutable c22 SHA-256 `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6` and normalized SHA-256 `e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77`.
- Lower only scalar i64 `math.absi`; leave i32, other widths, vectors/tensors, floating abs, and unrelated operations unchanged.
- Implement `%mask = arith.shrsi %x, 63`, `%bits = arith.xori %x, %mask`, `%abs = arith.subi %bits, %mask`.
- The subtraction must be unflagged. Do not add `nsw` or `nuw`: exact semantics require `abs(INT64_MIN) == INT64_MIN`, not poison or saturation.
- Do not fuse memory or downstream consumers; the authenticated sites cross distinct buffers and later loops.
- Permit only fixture-scoped CIRCT structural probing. Full-model Calyx, SV, synthesis, and board work remain forbidden until a clean authenticated receipt is independently reviewed.
- Use test-first development and commit every verified task.

---

### Task 1: Implement and Prove Scalar I64 AbsI Legalization

**Files:**
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`
- Modify: `tests/test_calyx_math_legalization.py`
- Create: `reproducers/calyx-math-absi/i64-signmask.mlir`
- Create: `scripts/pipeline/verify_i64_absi_signmask_semantics.py`
- Create: `tests/test_i64_absi_signmask_semantics.py`
- Create: `docs/results/2026-09-01-exact-tinystories-i64-absi-signmask-contract.md`

**Interfaces:**
- Consumes: scalar `math::AbsIOp` with i64 operand/result inside `llm2fpga-lower-exact-math-for-calyx`.
- Produces: constant 63:i64, `arith.shrsi`, `arith.xori`, and unflagged `arith.subi`, all at the original location.

- [ ] **Step 1: Write semantic and match-boundary REDs**

The independent oracle operates on all 64-bit encodings:

```python
MASK = (1 << 64) - 1
sign = MASK if bits & (1 << 63) else 0
lowered = ((bits ^ sign) - sign) & MASK
expected = bits if sign == 0 else (-bits) & MASK
assert lowered == expected
```

Cover zero, ±1, `INT64_MAX`, `INT64_MIN`, adjacent boundary values, powers of two, alternating patterns, and deterministic random encodings. Add matching scalar i64 plus nonmatching scalar i32 and vector<i64> fixtures. Require no overflow flags.

- [ ] **Step 2: Run REDs**

```bash
nix develop -c python -m unittest \
  tests/test_i64_absi_signmask_semantics.py \
  tests/test_calyx_math_legalization.py -v
```

Expected: oracle passes, while the plugin leaves scalar i64 `math.absi` and the bounded CIRCT probe rejects it.

- [ ] **Step 3: Extend the exact-math pass**

Collect scalar i64 `math::AbsIOp` before rewriting. At the original location create constant 63:i64, signed right shift, XOR, and unflagged subtraction, replace the abs, and preserve all nonmatches. Reuse the existing exact-math pass registration/dialect dependencies; do not add a new pipeline stage.

- [ ] **Step 4: Prove structure and bounded CIRCT acceptance**

Require the matching abs to disappear and exactly one each of `arith.shrsi`, `arith.xori`, and unflagged `arith.subi` to appear; reject `overflow<`, comparator/select/branch, and floating arithmetic. Require i32/vector controls to remain. Lower only the memory-backed matching function through pinned SCF-to-Calyx and require `calyx.std_srsh`, `calyx.std_xor`, `calyx.std_sub`, with no `math.absi`, `std_slt`, or `std_mux`.

- [ ] **Step 5: Verify and commit**

```bash
nix develop -c python -m unittest \
  tests/test_i64_absi_signmask_semantics.py \
  tests/test_calyx_math_legalization.py -v
nix build .#llm2fpgaMlirPasses -L
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add tools/mlir-passes/FoldConstantTruncFOps.cpp \
  reproducers/calyx-math-absi/i64-signmask.mlir \
  scripts/pipeline/verify_i64_absi_signmask_semantics.py \
  tests/test_i64_absi_signmask_semantics.py \
  tests/test_calyx_math_legalization.py \
  docs/results/2026-09-01-exact-tinystories-i64-absi-signmask-contract.md
git commit -m "feat: lower exact i64 absi"
```

Record the authoritative Nix plugin path and measured SHA-256.

### Task 2: Rotate Plugin Authority and Prove the Prepared Legality Result

**Files:**
- Modify: `flake.nix`
- Modify: `scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py`
- Modify: `tests/test_tinystories_1m_exact_normalized_registration.py`
- Modify: `docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md`
- Create: `docs/results/2026-09-01-exact-tinystories-i64-absi-successor.md`

**Interfaces:**
- Consumes: Task 1's reviewed plugin and unchanged exact preparation pipeline.
- Produces: freshly hash-bound prepared MLIR, legality receipt, manifest, and either the first residual or a clean pre-Calyx authorization record.

- [ ] **Step 1: Write stale-authority and successor REDs**

Require the old plugin hash to fail, independent preparation replay to produce `math.floor=0`, `arith.negf=0`, and `math.absi=0`, normalized SHA to remain unchanged, and no backend command in the registered closure. If the receipt is clean, require `calyx_authorized: true`; if any operation/diagnostic remains, require false and exact first-location evidence.

- [ ] **Step 2: Run REDs**

```bash
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py -v
```

Expected: stale plugin authority fails or the previous artifact still reports 1,156 absi operations.

- [ ] **Step 3: Rotate only the measured plugin identity**

Build Task 1's reviewed plugin, measure SHA-256, and update the plugin authority in `flake.nix`, verifier, and tests. Do not change c22, normalized, parser, checker, model, normalization pipeline, or preparation pipeline strings.

- [ ] **Step 4: Rebuild, independently replay, and classify**

```bash
nix build .#tiny-stories-1m-kev-gpt-exact-normalized-flat-scf -L
nix develop -c python \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py
nix develop -c python -m unittest \
  tests/test_tinystories_1m_exact_normalized_registration.py -v
```

Require all three carried blocker counts to be zero. Independently inspect the complete generic operation census and scanner diagnostics, rather than assuming the receipt is clean because the three named classes disappeared. If another prohibited/unknown/mapping diagnostic appears, record it as the sole next frontier. If the schema-v3 receipt is clean with no diagnostics, record `calyx_authorized: true` as eligibility for a separate full-model Calyx plan; do not invoke it here.

- [ ] **Step 5: Record identities, verify scope, and commit**

Record plugin, prepared, legality-file, receipt-self, and manifest hashes plus complete status/count/location evidence.

```bash
nix flake check --no-build
scripts/agent/pre_final_check.sh
git add flake.nix \
  scripts/pipeline/verify_tinystories_1m_exact_normalized_registration.py \
  tests/test_tinystories_1m_exact_normalized_registration.py \
  docs/results/2026-09-01-tinystories-1m-normalized-registration-precalyx.md \
  docs/results/2026-09-01-exact-tinystories-i64-absi-successor.md
git commit -m "feat: register exact i64 absi successor"
```

## Follow-Up Rule

- A residual or diagnostic authorizes only a plan for its earliest exact causal context.
- A clean authenticated receipt authorizes a separate full-model CIRCT/Calyx lowering plan, not an immediate success claim.
- SV, synthesis, and board work remain pending until full-model Calyx and SV artifacts are valid and independently verified.
