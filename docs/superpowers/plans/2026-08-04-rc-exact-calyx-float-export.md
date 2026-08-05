# RC Exact Calyx Float Export Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Preserve every Calyx f32 constant bit through native-Calyx SV export, prove the invariant, and resume the strict PT2E-to-Verilator equivalence ladder.

**Architecture:** Patch CIRCT's Calyx exporter so each calyx.constant emits raw IEEE-754 bits through Calyx's universal std_const primitive. Verify normalized Calyx MLIR against raw Futil before any compatibility normalizer can hide a precision defect. Bind the resulting receipt to strict SV cache and result evidence.

**Tech Stack:** CIRCT C++ patch applied by Nix overrideAttrs, Python 3 standard library, Nix, Calyx Futil/SystemVerilog, Verilator, unittest.

## Global Constraints

- PT2E exported.pt2 remains the only numerical acceptance authority.
- Preserve raw f32 bits, including signed zero, infinities, and NaN payloads; never use formatted decimal or a host float as the authority for existing bit patterns.
- Fix the compiler/backend boundary; do not use a textual post-export Futil repair as the production path.
- Verify raw Futil before normalize_futil_float_constants.py; a legacy std_float_const is an error in this exact route.
- Passing the constant proof does not establish model equivalence. Required acceptance remains regenerated zero, frozen four, then all 1,679,616 lexical contexts.

---

### Task 1: Patch CIRCT's Calyx exporter

**Files:**

- Create: patches/circt/0001-export-calyx-float-constants-as-raw-bits.patch
- Modify: flake.nix lines 41-53
- Modify through the patch: lib/Dialect/Calyx/Export/CalyxEmitter.cpp
- Modify through the patch: test/Dialect/Calyx/emit.mlir
- Create: reproducers/calyx-exact-float-export/input.mlir
- Create: diagnostics/rc-calyx-exact-float-export.nix

**Interfaces:**

- Emitter::emitConstant(ConstantOp) emits std_const(width, unsigned_raw_word).
- ImportTracker::getLibraryFor(ConstantOp) returns compile.
- The Nix self-test emits receipt.json and proves exact normal, tiny, signed-zero, infinite, and NaN words.

- [ ] **Step 1: Write the failing export regression**

Create one constant-only Calyx component containing:

~~~mlir
%tiny = calyx.constant @tiny <7.54663105e-08 : f32> : i32
%neg_zero = calyx.constant @neg_zero <0x80000000 : f32> : i32
%pos_inf = calyx.constant @pos_inf <0x7F800000 : f32> : i32
%nan = calyx.constant @nan <0x7FC00001 : f32> : i32
%four_point_two = calyx.constant @four_point_two <4.200000e+00 : f32> : i32
~~~

Make the Nix self-test run circt-translate --export-calyx and require:

~~~text
import "primitives/compile.futil";
tiny = std_const(32, 866258955);
neg_zero = std_const(32, 2147483648);
pos_inf = std_const(32, 2139095040);
nan = std_const(32, 2143289345);
four_point_two = std_const(32, 1082549862);
~~~

It must reject std_float_const and primitives/float.futil. Add it to the flake package set and demonstrate failure against the unpatched exporter.

- [ ] **Step 2: Implement the source-level fix**

Replace Emitter::emitConstant's decimal path:

~~~c++
double doubleValue = value.convertToDouble();
... << "std_float_const";
... << std::to_string(doubleValue)
~~~

with:

~~~c++
APInt rawBits = value.bitcastToAPInt();
SmallString<32> rawBitsDecimal;
rawBits.toStringUnsigned(rawBitsDecimal, /*Radix=*/10);
... << "std_const";
os << LParen() << floatBits << comma() << rawBitsDecimal << RParen()
   << semicolonEndL();
~~~

Change the ConstantOp import from float to compile. Update the CIRCT golden checks for 4.2, negative, infinity, and NaN examples, and add tiny plus signed-zero coverage.

- [ ] **Step 3: Wire and verify the patch**

Append the patch to the existing circt.overrideAttrs patch list without changing flake.lock. Run:

~~~bash
nix build .#rc-calyx-exact-float-export -L
python3 -m unittest tests.test_calyx_export_normalization -v
git diff --check
~~~

Expected: the Nix receipt contains all five words exactly and the unit tests pass.

- [ ] **Step 4: Commit Task 1**

~~~bash
git add flake.nix patches/circt/0001-export-calyx-float-constants-as-raw-bits.patch
git add reproducers/calyx-exact-float-export/input.mlir
git add diagnostics/rc-calyx-exact-float-export.nix tests/test_calyx_export_normalization.py
git commit -m "fix: preserve Calyx float constants at CIRCT export"
~~~

### Task 2: Add a fail-closed Calyx-to-Futil bit verifier

**Files:**

- Create: scripts/pipeline/verify_calyx_f32_constant_bits.py
- Create: tests/test_calyx_f32_constant_bits.py
- Modify: scripts/pipeline/calyx_to_sv_no_handshake.sh lines 64-94
- Modify: tests/test_calyx_export_normalization.py
- Modify: flake.nix lines 808-818

**Interfaces:**

- CLI: verify_calyx_f32_constant_bits.py --calyx-mlir PATH --futil PATH --receipt PATH.
- Schema: rc-calyx-f32-constant-bits-v1, with source/Futil SHA-256 values and sorted component, symbol, word_u32 rows.
- It accepts only a one-to-one exact mapping from source component/constant-symbol to raw-Futil std_const(32, word).

- [ ] **Step 1: Write failing parser and receipt tests**

Cover exact success, tiny nonzero changed to zero, signed zero, missing/extra keys, duplicate keys, wrong width, and legacy std_float_const.

~~~python
def test_rejects_tiny_nonzero_rewritten_as_zero(self):
    result = run_verifier(
        source="calyx.constant @tiny <7.54663105e-08 : f32> : i32",
        futil="tiny = std_const(32, 0);",
    )
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("866258955", result.stderr)

def test_accepts_exact_negative_zero_word(self):
    receipt = run_verifier_success(
        source="calyx.constant @neg_zero <0x80000000 : f32> : i32",
        futil="neg_zero = std_const(32, 2147483648);",
    )
    self.assertEqual(receipt["constants"][0]["word_u32"], 2147483648)
~~~

- [ ] **Step 2: Verify RED**

~~~bash
python3 -m unittest tests.test_calyx_f32_constant_bits -v
~~~

Expected: FAIL because the verifier does not exist.

- [ ] **Step 3: Implement exact matching**

Parse hexadecimal f32 literals directly. Convert finite source decimal literals with a new pure helper decimal_literal_to_f32_word(literal: str) -> int: parse the sign, coefficient, decimal exponent, and rational value with decimal.Decimal and fractions.Fraction; select the IEEE binary32 exponent; divide and round the 24-bit significand with round-half-to-even; then handle subnormal, overflow-to-infinity, and signed zero explicitly. Do not call float(), numpy, or struct.pack on a host float for source decimal authority. Parse raw Futil by component and cell, accepting only std_const(32, 0..4294967295). Reject duplicates, missing/extra keys, wrong widths, legacy float cells, and any mismatched word. Write canonical JSON only after every check succeeds.

- [ ] **Step 4: Enforce the verifier before normalization**

Immediately after successful circt-translate --export-calyx, invoke:

~~~bash
python3 "$verify_futil_bits" \
  --calyx-mlir "$tmp_normalized" \
  --futil "$tmp_exported_futil" \
  --receipt "$output_dir/f32-constant-bits.json"
~~~

Export CALYX_VERIFY_F32_CONSTANT_BITS from every RC native-SV Nix derivation. Keep the existing normalizer downstream only as an identity-compatible legacy helper; it must never precede verification.

- [ ] **Step 5: Verify GREEN and commit Task 2**

~~~bash
python3 -m unittest tests.test_calyx_f32_constant_bits tests.test_calyx_export_normalization -v
python3 -m py_compile scripts/pipeline/verify_calyx_f32_constant_bits.py
git diff --check
git add scripts/pipeline/verify_calyx_f32_constant_bits.py
git add scripts/pipeline/calyx_to_sv_no_handshake.sh
git add tests/test_calyx_f32_constant_bits.py tests/test_calyx_export_normalization.py flake.nix
git commit -m "test: bind Calyx Futil constants to source float bits"
~~~

### Task 3: Bind the proof to strict equivalence and regenerate SV

**Files:**

- Modify: scripts/pipeline/run_rc_sv_equivalence.py
- Modify: tests/test_rc_observable_driver.py
- Modify: flake.nix lines 819-881
- Modify: diagnostics/rc-observable-equivalence.nix

**Interfaces:**

- Strict runner option: --f32-constant-bits receipt.json.
- Strict cache/result/counterexample metadata includes its SHA-256.
- The frozen-four Nix derivation consumes the regenerated f32-constant-bits.json.

- [ ] **Step 1: Write failing strict receipt tests**

~~~python
def test_strict_mode_rejects_missing_exact_constant_receipt(self):
    with self.assertRaisesRegex(RuntimeError, "f32 constant"):
        module._validate_f32_constant_bits_receipt(None, strict=True)

def test_cache_identity_changes_with_constant_receipt(self):
    self.assertNotEqual(
        module._compile_identity(..., f32_constant_bits_sha256="a" * 64),
        module._compile_identity(..., f32_constant_bits_sha256="b" * 64),
    )
~~~

Reject wrong schema, nonzero mismatch count, source/Futil hash drift, and a cache built with another receipt hash.

- [ ] **Step 2: Implement and verify strict receipt binding**

Load and validate the receipt before compile/cache lookup; record its SHA in compile metadata, timing, pass receipt, and durable failure counterexample. Run:

~~~bash
python3 -m unittest tests.test_rc_observable_driver tests.test_rc_sv_equivalence_fixture -v
python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py
git diff --check
~~~

- [ ] **Step 3: Use the regenerated artifact for the actual gate**

Pass the f32-constant-bits receipt to build and run derivations. Replace legacy static-reference execution with the existing generic frozen-four shard gate: four fresh processes plus one sequential-reset process, all requiring six exact raw codes and lowest-index argmax.

- [ ] **Step 4: Commit Task 3**

~~~bash
git add scripts/pipeline/run_rc_sv_equivalence.py tests/test_rc_observable_driver.py
git add flake.nix diagnostics/rc-observable-equivalence.nix
git commit -m "feat: bind strict RC equivalence to exact Calyx constants"
~~~

### Task 4: Run the full acceptance ladder

**Files:** Generated Nix outputs only; do not check temporary simulator work directories into git.

- [ ] **Step 1: Rebuild the exact SV artifact**

~~~bash
nix build .#tinystories-w8a8-rc-polynomial-exp-sv -L
~~~

Require f32-constant-bits.json to report 77 constants, zero mismatches, and source/Futil hashes. Require model.futil to contain no std_float_const and cst_55 = std_const(32, 866258955).

- [ ] **Step 2: Run regenerated frozen four**

~~~bash
nix build .#tinystories-w8a8-rc-observable-equivalence-frozen-four -L
~~~

Require four fresh-process receipts and one sequential-reset receipt, all pass with raw codes and lowest-index argmax.

- [ ] **Step 3: Run and merge exhaustive deterministic shards**

Launch only after frozen-four PASS. Merge only matching PT2E/reference/image/SV/constant-proof/ABI/fixture hashes. Require exact half-open lexical coverage [0, 1679616) with no overlaps, gaps, or duplicates.

- [ ] **Step 4: Completion audit**

~~~bash
git diff --check
nix flake check -L
~~~

Inspect the frozen-four and merged manifests against this plan and docs/superpowers/plans/2026-08-04-rc-observable-equivalence.md before calling the goal complete.
