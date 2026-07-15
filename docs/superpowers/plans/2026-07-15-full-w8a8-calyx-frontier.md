# Full W8A8 Calyx Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the full frozen TinyStories PT2E W8A8 Direct-Linalg/no-handshake route pass its exact `arith.uitofp i1 -> f32` Calyx frontier, correctly classify flat-SCF residuals, and rerun the real route through every newly available downstream artifact.

**Architecture:** Preserve the existing full `tinystories-w8a8` model and Direct-Linalg route. Add one narrow pre-Calyx MLIR pass that converts only boolean-to-f32 unsigned casts into CIRCT-supported `extui` plus `sitofp`, then add explicit evidence at the pre-Calyx boundary. Keep flat-SCF residual information, but report it as a completed stage with residuals because the existing pre-Calyx normalizer consumes those forms.

**Tech Stack:** Nix flakes, MLIR C++ pass plugin, CIRCT `--lower-scf-to-calyx`, Python `unittest`, Python diagnostic scripts, Calyx, yosys-slang, nextpnr-xilinx.

## Global Constraints

- Work on user-approved `main`; do not modify or stage the existing `docs/glossary.md` change.
- The input remains exactly the registered full `tinystories-w8a8`: TinyStories-1M, frozen single-token-zero-input calibration, and XNNPACK PT2E static W8A8 export.
- The active route remains `frontend = "linalg"`, `pipelineStagePackagesNoHandshake`, `noHandshakeLinalgStages`, and `backend = "calyx-native-sv"`; add no TOSA stage or package.
- Do not modify the model, PyTorch graph, calibration, quantizer, or existing approximate math-scout policy.
- The legalization may match only `arith.uitofp i1 -> f32`; it must not rewrite wider unsigned conversions or other float result types.
- Keep durable evidence in repository files and Nix outputs. Do not run `nix gc`, delete store paths, or create durable `/tmp` artifacts. Do not impose an arbitrary short cutoff.
- This remains a resource scout, not an equivalence, board-validation, or SmoothQuant result.
- Native SV, RTLIL, mapping, and nextpnr must remain gated on real upstream artifacts; do not generate placeholders.

---

## File structure

| File | Responsibility |
|---|---|
| `reproducers/calyx-i1-uitofp/input.mlir` | Minimal upstream CIRCT failure case for the exact unsupported cast. |
| `reproducers/calyx-i1-uitofp/nonmatching.mlir` | Boundary cases the new pass must leave as `arith.uitofp`. |
| `reproducers/calyx-i1-uitofp/README.md` | Scope, command, semantics, and non-textual-fix contract. |
| `tools/mlir-passes/FoldConstantTruncFOps.cpp` | Registered narrow MLIR legalization pass. |
| `nix/pipeline.nix` | Insert pass and pre-Calyx clean-boundary check into the no-handshake Calyx derivation. |
| `scripts/diagnostics/flat_scf_blocker_report.py` | Represent raw flattening residuals without misreporting stage execution as blocked. |
| `scripts/pipeline/calyx_preflight_report.py` | Emit a machine-readable pre-Calyx legality census and return failure on prohibited residuals. |
| `scripts/pipeline/calyx_float_frontier_report.py` | Count `arith.uitofp` accurately if it appears in a diagnostic input. |
| `scripts/pipeline/scf_to_calyx_no_handshake.sh` | Preserve a checked pre-Calyx failure as a normal Calyx-stage diagnostic artifact. |
| `flake.nix` | Expose reproducible upstream-failure and fixed-pass selftests. |
| `tests/test_representative_core_no_handshake_sv.py` | Static contract coverage for pass registration, ordering, reproducibility assets, and flat-SCF status. |
| `tests/test_calyx_preflight_report.py` | Behavioral unit tests for the new legality census. |
| `tests/test_flat_scf_blocker_report.py` | Behavioral coverage for truthful flat-SCF manifest status. |
| `tests/test_direct_linalg_xc7k480t_utilization.py` | Static contract coverage for a full-model XC7K480T mapper and P&R wrapper, if RTLIL becomes real. |
| `docs/results/2026-07-15-full-w8a8-direct-linalg-scout.md` | Replace the old frontier with the factual post-fix result only after the full rerun. |

### Task 1: Capture the pinned upstream `i1`-to-`f32` failure

**Files:**
- Create: `reproducers/calyx-i1-uitofp/input.mlir`
- Create: `reproducers/calyx-i1-uitofp/README.md`
- Modify: `flake.nix`
- Modify: `tests/test_representative_core_no_handshake_sv.py`

**Interfaces:**
- Consumes: packaged `circt` and the exact `--lower-scf-to-calyx='top-level-function=main'` invocation.
- Produces: package `calyx-i1-uitofp-upstream-reproducer`, which succeeds only when CIRCT rejects the intentionally unsupported input and preserves `lower.log` in its Nix output.

- [ ] **Step 1: Write the failing static contract test**

  Add this method to `RepresentativeCoreNoHandshakeSvTest`:

  ```python
  def test_calyx_i1_uitofp_frontier_is_minimized(self) -> None:
      reproducer_dir = REPO_ROOT / "reproducers" / "calyx-i1-uitofp"
      input_mlir = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
      readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")
      flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

      self.assertIn("arith.uitofp", input_mlir)
      self.assertIn(": i1 to f32", input_mlir)
      self.assertIn("extui", readme)
      self.assertIn("sitofp", readme)
      self.assertIn("Textual MLIR substitution is not an acceptable fix", readme)
      self.assertIn('"calyx-i1-uitofp-upstream-reproducer"', flake)
  ```

- [ ] **Step 2: Run the test to verify RED**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_calyx_i1_uitofp_frontier_is_minimized \
    -v
  ```

  Expected: `FileNotFoundError` because `reproducers/calyx-i1-uitofp/` does not exist.

- [ ] **Step 3: Add the minimal input and explanation**

  Create `input.mlir` exactly as:

  ```mlir
  module {
    func.func @main(%input: memref<1xi1>, %output: memref<1xf32>) {
      %c0 = arith.constant 0 : index
      %predicate = memref.load %input[%c0] : memref<1xi1>
      %value = arith.uitofp %predicate : i1 to f32
      memref.store %value, %output[%c0] : memref<1xf32>
      return
    }
  }
  ```

  Write `README.md` with this exact command and contract:

  ```sh
  circt-opt input.mlir --lower-scf-to-calyx='top-level-function=main'
  ```

  State that the result is rejected because the pinned conversion does not
  lower `arith.uitofp`, that i1 has only values 0 and 1, that the intended
  exact lowering is `extui i1 -> i32` then `sitofp i32 -> f32`, and that
  textual MLIR substitution is not an acceptable fix.

- [ ] **Step 4: Add the expected-failure Nix package**

  Near the existing Calyx selftests in `flake.nix`, define:

  ```nix
  calyxI1UiToFpUpstreamReproducer = pkgs.runCommand
    "calyx-i1-uitofp-upstream-reproducer" {
      nativeBuildInputs = [ circt ];
    } ''
      mkdir -p "$out"
      set +e
      ${circt}/bin/circt-opt \
        ${./reproducers/calyx-i1-uitofp/input.mlir} \
        --lower-scf-to-calyx='top-level-function=main' \
        -o "$out/model.calyx.mlir" >"$out/lower.log" 2>&1
      rc=$?
      set -e
      test "$rc" -ne 0
      ${pkgs.gnugrep}/bin/grep -F \
        "failed to legalize operation 'arith.uitofp'" "$out/lower.log"
    '';
  ```

  Export it as `"calyx-i1-uitofp-upstream-reproducer"` in `packages` and as
  `checks.calyx-i1-uitofp-upstream-reproducer`.

- [ ] **Step 5: Verify GREEN**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_calyx_i1_uitofp_frontier_is_minimized \
    -v
  nix build .#calyx-i1-uitofp-upstream-reproducer -L --no-link
  ```

  Expected: Python test passes; Nix output contains `lower.log` with the
  known `arith.uitofp` legalization failure.

- [ ] **Step 6: Commit Task 1**

  ```sh
  git add reproducers/calyx-i1-uitofp flake.nix \
    tests/test_representative_core_no_handshake_sv.py
  git commit -m "test: capture calyx i1 uitofp frontier"
  ```

### Task 2: Add the exact pre-Calyx boolean-to-float legalization

**Files:**
- Modify: `tools/mlir-passes/FoldConstantTruncFOps.cpp`
- Modify: `nix/pipeline.nix`
- Modify: `flake.nix`
- Create: `reproducers/calyx-i1-uitofp/nonmatching.mlir`
- Modify: `tests/test_representative_core_no_handshake_sv.py`

**Interfaces:**
- Consumes: `arith::UIToFPOp` with input `i1` and result `f32`.
- Produces: pass argument `llm2fpga-lower-i1-uitofp-for-calyx` and package `calyx-i1-uitofp-legalization-selftest`.
- Invariant: the pass replaces each matching operation with one `arith.extui i1 -> i32` followed by one `arith.sitofp i32 -> f32`; it leaves every nonmatching `arith.uitofp` untouched.

- [ ] **Step 1: Write the failing pass/pipeline contract test**

  Add this method to `RepresentativeCoreNoHandshakeSvTest`:

  ```python
  def test_pre_calyx_legalizes_only_i1_uitofp_to_f32(self) -> None:
      source = (REPO_ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp").read_text(encoding="utf-8")
      pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
      flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

      self.assertIn("llm2fpga-lower-i1-uitofp-for-calyx", source)
      self.assertIn("arith::UIToFPOp", source)
      self.assertIn("isInteger(1)", source)
      self.assertIn("isF32()", source)
      self.assertIn("arith::ExtUIOp", source)
      self.assertIn("arith::SIToFPOp", source)
      self.assertIn("PassRegistration<LowerI1UIToFPForCalyxPass>", source)
      self.assertIn("llm2fpga-lower-i1-uitofp-for-calyx", pipeline)
      self.assertIn('"calyx-i1-uitofp-legalization-selftest"', flake)
  ```

- [ ] **Step 2: Run the test to verify RED**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_pre_calyx_legalizes_only_i1_uitofp_to_f32 \
    -v
  ```

  Expected: FAIL because the new pass and selftest are absent.

- [ ] **Step 3: Implement the narrow pass**

  In `FoldConstantTruncFOps.cpp`, add `LowerI1UIToFPForCalyxPass` alongside
  the existing pre-Calyx passes. Its core operation must be:

  ```c++
  void lower(arith::UIToFPOp op, IRRewriter &rewriter) {
    auto sourceType = dyn_cast<IntegerType>(op.getIn().getType());
    auto resultType = dyn_cast<FloatType>(op.getType());
    if (!sourceType || !sourceType.isInteger(1) || !resultType ||
        !resultType.isF32())
      return;

    rewriter.setInsertionPoint(op);
    Value widened = arith::ExtUIOp::create(
        rewriter, op.getLoc(), rewriter.getI32Type(), op.getIn());
    Value replacement = arith::SIToFPOp::create(
        rewriter, op.getLoc(), resultType, widened);
    rewriter.replaceOp(op, replacement);
  }
  ```

  Collect matching `arith::UIToFPOp` operations before rewriting, register the
  Arith dialect, declare and define the pass type ID, and register it in
  `mlirGetPassPluginInfo()`.

  Create `reproducers/calyx-i1-uitofp/nonmatching.mlir` with both an
  `arith.uitofp i8 -> f32` and an `arith.uitofp i1 -> f64` operation. It is a
  pass-boundary fixture, not a CIRCT-success fixture: both operations must
  remain untouched after the pass.

- [ ] **Step 4: Insert the pass at the correct boundary**

  In `mkScfToCalyxDerivation`, append the pass after
  `llm2fpga-lower-exact-math-for-calyx${scoutMathPass}` and before
  `canonicalize,cse`:

  ```text
  ...,llm2fpga-lower-exact-math-for-calyx${scoutMathPass},llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)
  ```

  Do not change the route, model name conditional, or any TOSA configuration.

- [ ] **Step 5: Add the positive Nix selftest**

  Define and export `calyxI1UiToFpLegalizationSelftest` in `flake.nix`.
  It must run the new plugin pass on the Task 1 input, assert the lowered MLIR
  contains `arith.extui` and `arith.sitofp` and no `arith.uitofp`, then lower
  that result with CIRCT and require a nonempty `model.calyx.mlir`. It must
  also run the same pass on `nonmatching.mlir` and assert that both original
  `arith.uitofp` operations remain. That makes the `i1 -> f32` boundary an
  executable invariant rather than a source-text-only claim.

  ```nix
  ${mlir}/bin/mlir-opt ${./reproducers/calyx-i1-uitofp/input.mlir} \
    --load-pass-plugin=${llm2fpgaMlirPasses}/lib/LLM2FPGAMLIRPasses.so \
    --pass-pipeline='builtin.module(llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)' \
    -o "$out/lowered.mlir"
  ```

  Use shell `grep` tests, not textual transformation, and run:

  ```sh
  ${circt}/bin/circt-opt "$out/lowered.mlir" \
    --lower-scf-to-calyx='top-level-function=main' \
    -o "$out/model.calyx.mlir" >"$out/lower.log" 2>&1
  test -s "$out/model.calyx.mlir"
  ```

- [ ] **Step 6: Verify GREEN**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_pre_calyx_legalizes_only_i1_uitofp_to_f32 \
    -v
  nix build .#calyx-i1-uitofp-legalization-selftest -L --no-link
  ```

  Expected: the static test passes and the Nix selftest produces a nonempty
  Calyx MLIR artifact.

- [ ] **Step 7: Commit Task 2**

  ```sh
  git add tools/mlir-passes/FoldConstantTruncFOps.cpp nix/pipeline.nix \
    flake.nix reproducers/calyx-i1-uitofp/nonmatching.mlir \
    tests/test_representative_core_no_handshake_sv.py
  git commit -m "feat: legalize calyx i1 uitofp"
  ```

### Task 3: Make flat-SCF and pre-Calyx evidence truthful and enforceable

**Files:**
- Modify: `scripts/diagnostics/flat_scf_blocker_report.py`
- Create: `scripts/pipeline/calyx_preflight_report.py`
- Modify: `scripts/pipeline/calyx_float_frontier_report.py`
- Modify: `scripts/pipeline/scf_to_calyx_no_handshake.sh`
- Modify: `nix/pipeline.nix`
- Create: `tests/test_calyx_preflight_report.py`
- Modify: `tests/test_flat_scf_blocker_report.py`
- Modify: `tests/test_representative_core_no_handshake_sv.py`

**Interfaces:**
- Consumes: normalized pre-Calyx MLIR.
- Produces: `pre-calyx-legality.json` with `status`, `prohibited_ops`, and per-operation counts.
- Invariant: `memref.reinterpret_cast`, `memref.expand_shape`, `memref.collapse_shape`, `memref.copy`, and `arith.uitofp` must all have count zero before CIRCT runs.

- [ ] **Step 1: Write failing behavioral tests for the census and status**

  Create `tests/test_calyx_preflight_report.py` using the same subprocess and
  temporary-directory pattern as `tests/test_calyx_float_frontier_report.py`.
  Its `run_report(mlir, require_clean=False)` helper must write an input file,
  invoke the script, parse the generated JSON even on a nonzero return, and
  return `(returncode, report)`. Add these two tests:

  ```python
  def test_preflight_fails_for_each_prohibited_operation(self) -> None:
      rc, report = self.run_report(
          "memref.copy %a, %b : memref<1xi8> to memref<1xi8>\n"
          "%0 = arith.uitofp %flag : i1 to f32\n",
          require_clean=True,
      )
      self.assertEqual(rc, 1)
      self.assertEqual(report["status"], "blocked")
      self.assertEqual(report["prohibited_ops"], {
          "arith.uitofp": 1,
          "memref.copy": 1,
      })

  def test_preflight_accepts_clean_scalar_mlir(self) -> None:
      rc, report = self.run_report(
          "%0 = arith.sitofp %arg0 : i32 to f32\n", require_clean=True
      )
      self.assertEqual(rc, 0)
      self.assertEqual(report["status"], "ok")
      self.assertEqual(report["prohibited_ops"], {})
  ```

  Extend `tests/test_flat_scf_blocker_report.py` with a behavioral manifest
  test: invoke the existing script with `--manifest-output` on input that has
  a residual view or copy, parse the manifest, and require
  `status == "completed-with-residuals"`. Keep the existing count and location
  tests unchanged.

- [ ] **Step 2: Run the tests to verify RED**

  Run:

  ```sh
  python3 -m unittest tests.test_calyx_preflight_report -v
  python3 -m unittest \
    tests.test_flat_scf_blocker_report.FlatScfBlockerReportTest.test_manifest_reports_completed_with_residuals \
    -v
  ```

  Expected: a missing-script failure for the census test and an assertion
  failure for the old flat-SCF status contract.

- [ ] **Step 3: Implement the two reports**

  In `flat_scf_blocker_report.py`, keep the existing `blockers.json` structure
  and counts but make `build_manifest` return `status: "completed-with-residuals"`
  whenever `report["blockers"]` is nonempty; return `"ok"` when it is empty.

  Create `calyx_preflight_report.py` with:

  ```python
  PROHIBITED_PATTERNS = {
      "arith.uitofp": re.compile(r"\\barith\\.uitofp\\b"),
      "memref.collapse_shape": re.compile(r"\\bmemref\\.collapse_shape\\b"),
      "memref.copy": re.compile(r"\\bmemref\\.copy\\b"),
      "memref.expand_shape": re.compile(r"\\bmemref\\.expand_shape\\b"),
      "memref.reinterpret_cast": re.compile(r"\\bmemref\\.reinterpret_cast\\b"),
  }

  def build_report(text: str) -> dict[str, object]:
      prohibited_ops = {
          name: len(pattern.findall(text))
          for name, pattern in PROHIBITED_PATTERNS.items()
          if pattern.search(text)
      }
      return {
          "status": "blocked" if prohibited_ops else "ok",
          "prohibited_ops": prohibited_ops,
      }
  ```

  Give the script positional `input` and `output` arguments, write sorted
  indented JSON, and exit 1 only when `--require-clean` is passed and the
  generated report status is `blocked`.

  In `calyx_float_frontier_report.py`, add `arith.uitofp` to `FLOAT_OP_RE` and
  to `UNSUPPORTED_CALYX_FLOAT_OPS`, so an unnormalized diagnostic input cannot
  claim the cast is outside the scanner's scope.

- [ ] **Step 4: Run and preserve the pre-Calyx assertion**

  Do not let a future preflight regression become an opaque failed Nix build.
  In `mkScfToCalyxDerivation`, export:

  ```sh
  export CALYX_PREFLIGHT_REPORT=${pipelineScripts}/calyx_preflight_report.py
  ```

  before invoking `scf_to_calyx_no_handshake.sh`, and add
  `test -f "$out/pre-calyx-legality.json"` alongside the existing artifact
  checks.

  In `scf_to_calyx_no_handshake.sh`, after copying the normalized input to the
  output directory and before invoking CIRCT, run the report with
  `--require-clean` under a captured exit status. If it returns nonzero, keep
  `flat.scf.mlir` and `pre-calyx-legality.json`, write the established
  Calyx-style `manifest.json` with `status: "failed"`, reason
  `"pre-Calyx legality census found prohibited operations"`, and a reference
  to the report, then exit zero. If it returns zero, run CIRCT unchanged.

  This is a real assertion at the actual CIRCT boundary while preserving the
  durable diagnostic convention used by the existing Calyx stage. Extend
  `test_pre_calyx_uses_checked_in_mlir_pass_plugin` to assert the exported
  preflight path, `--require-clean`, and the new artifact name.

- [ ] **Step 5: Verify GREEN**

  Run:

  ```sh
  python3 -m unittest tests.test_calyx_preflight_report -v
  python3 -m unittest \
    tests.test_flat_scf_blocker_report -v
  python3 -m unittest \
    tests.test_representative_core_no_handshake_sv.RepresentativeCoreNoHandshakeSvTest.test_pre_calyx_uses_checked_in_mlir_pass_plugin \
    -v
  nix flake check --no-build
  ```

  Expected: both Python suites pass and Nix evaluates the new script wiring.

- [ ] **Step 6: Commit Task 3**

  ```sh
  git add scripts/diagnostics/flat_scf_blocker_report.py \
    scripts/pipeline/calyx_preflight_report.py \
    scripts/pipeline/calyx_float_frontier_report.py \
    scripts/pipeline/scf_to_calyx_no_handshake.sh nix/pipeline.nix \
    tests/test_calyx_preflight_report.py tests/test_flat_scf_blocker_report.py \
    tests/test_representative_core_no_handshake_sv.py
  git commit -m "fix: validate calyx preflight boundary"
  ```

### Task 4: Run the actual full model and advance only through real artifacts

**Files:**
- Modify: `docs/results/2026-07-15-full-w8a8-direct-linalg-scout.md`
- Modify: `tests/test_full_tinystories_w8a8_scout.py`

**Interfaces:**
- Consumes: `tinystories-w8a8-via-linalg-no-handshake-calyx` and its complete pre-Calyx evidence.
- Produces: an updated factual result with exact immutable paths and no claim beyond the last generated artifact.

- [ ] **Step 1: Add the failing result-contract test**

  Add a test that reads the result document and requires all of:

  ```python
  self.assertIn("completed-with-residuals", doc)
  self.assertIn("pre-calyx-legality.json", doc)
  self.assertNotIn("flat-SCF artifact whose manifest is `blocked`", doc)
  ```

- [ ] **Step 2: Verify RED**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_full_tinystories_w8a8_scout.FullTinyStoriesW8A8ScoutTest.test_full_linalg_scout_records_postfix_boundary \
    -v
  ```

  Expected: FAIL because the historical report still says `blocked` and has no
  pre-Calyx legality artifact.

- [ ] **Step 3: Build the real Calyx stage without an arbitrary cutoff**

  Run:

  ```sh
  nix build .#tinystories-w8a8-via-linalg-no-handshake-calyx \
    -L --no-link --print-out-paths
  ```

  Inspect `manifest.json`, `pre-calyx-legality.json`, `float-frontier.json`,
  `lower-scf-to-calyx.log`, and, if present, `model.calyx.mlir`. Record every
  immutable output path in the result document.

- [ ] **Step 4: Continue conditionally through real downstream artifacts**

  If the Calyx manifest is `status: ok`, run these commands in order, stopping
  at the first factual frontier and recording it:

  ```sh
  nix build .#tinystories-w8a8-via-linalg-no-handshake-calyx-native-sv \
    -L --no-link --print-out-paths
  nix build .#tinystories-w8a8-via-linalg-no-handshake-il \
    -L --no-link --print-out-paths
  nix build .#tinystories-w8a8-via-linalg-no-handshake-yosys-stat \
    -L --no-link --print-out-paths
  ```

  If RTLIL is generated, proceed to Task 5's existing-flow mapper and P&R
  implementation before claiming mapped utilization. The source RTLIL must be
  the full alias above, the top must be verified from the generated RTLIL, and
  the target must remain `xc7k480tffg1156-1`.

  If Calyx is not `ok`, do not invoke native SV, Yosys, mapping, or P&R.

- [ ] **Step 5: Write bounded evidence and verify GREEN**

  Update the result document with:

  - full-model provenance and no-TOSA route;
  - raw flat-SCF residual status and the clean pre-Calyx census;
  - the new Calyx result or exact next terminal diagnostic;
  - downstream stages actually attempted and their status;
  - explicit absence of equivalence and unsupported resource claims.

  Then run:

  ```sh
  python3 -m unittest tests.test_full_tinystories_w8a8_scout -v
  nix flake check --no-build
  git diff --check
  ```

- [ ] **Step 6: Commit Task 4**

  ```sh
  git add docs/results/2026-07-15-full-w8a8-direct-linalg-scout.md \
    tests/test_full_tinystories_w8a8_scout.py
  git commit -m "docs: advance full w8a8 calyx frontier"
  ```

### Task 5: Conditionally reuse the established XC7K480T mapper and P&R flow

**Precondition:** Task 4 generated full-model RTLIL at
`tinystories-w8a8-via-linalg-no-handshake-il` and its top-level module has
been verified as `main`.

**Files:**
- Modify: `flake.nix`
- Modify: `tests/test_direct_linalg_xc7k480t_utilization.py`
- Modify: `docs/results/2026-07-15-full-w8a8-direct-linalg-scout.md`

**Interfaces:**
- Consumes: actual full-model RTLIL, existing `task3MainLib.mkTask3XilinxUtilization`, existing `task3MainLib.mkTask3XilinxPnrReport`, and the pinned XC7K480T target.
- Produces: `tinystories-w8a8-via-linalg-no-handshake-xc7k480t-{mapped-utilization,mapped-json,probe-xdc,nextpnr-utilization}`.
- Invariant: this is the exact full frozen W8A8 Direct-Linalg/no-handshake RTLIL, with top `main`, target `xc7k480tffg1156-1`, and only the four P&R probe ports constrained.

- [ ] **Step 1: Verify the artifact precondition and write the failing wiring test**

  Run:

  ```sh
  nix build .#tinystories-w8a8-via-linalg-no-handshake-il \
    -L --no-link --print-out-paths
  ```

  Inspect the emitted RTLIL and confirm it defines top `main` with `clk`,
  `reset`, `go`, and `done` ports. If this command cannot produce RTLIL,
  mark Task 5 inapplicable and do not add mapper declarations.

  If it succeeds, add a test mirroring the existing direct-Linalg integer
  mapper test, but with these exact names:

  ```python
  route_name = "tinystories-w8a8-via-linalg-no-handshake-xc7k480t"
  source_alias = "tinystories-w8a8-via-linalg-no-handshake-il"
  ```

  Require `modelIl = pipelineAliasPackages."${source_alias}"`,
  `topName = "main"`, `capacities = task3TinyStoriesCapacities`, target part
  `xc7k480tffg1156-1`, and all four public package names in the interface
  contract above.

- [ ] **Step 2: Run the wiring test to verify RED**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_direct_linalg_xc7k480t_utilization.DirectLinalgXc7k480tUtilizationTest.test_root_flake_wires_full_w8a8_direct_linalg_xc7k480t_mapper_and_pnr \
    -v
  ```

  Expected: FAIL because full-model mapping/P&R packages do not yet exist.

- [ ] **Step 3: Add the full-model staged mapper declarations**

  In `flake.nix`, duplicate the existing direct-Linalg integer mapper pattern
  under these exact bindings:

  ```nix
  fullW8A8DirectLinalgXc7k480tRouteName =
    "tinystories-w8a8-via-linalg-no-handshake-xc7k480t";
  fullW8A8DirectLinalgXc7k480tSynthesis = task3MainLib.mkTask3XilinxUtilization {
    name = fullW8A8DirectLinalgXc7k480tRouteName;
    modelIl = pipelineAliasPackages."tinystories-w8a8-via-linalg-no-handshake-il";
    topName = "main";
    capacities = task3TinyStoriesCapacities;
    quiet = true;
  };
  ```

  Create the same four-port, P&R-only XDC as the established integer route:

  ```tcl
  set_property PACKAGE_PIN AA28 [get_ports {clk}]
  set_property PACKAGE_PIN R28 [get_ports {reset}]
  set_property PACKAGE_PIN P30 [get_ports {go}]
  set_property PACKAGE_PIN M30 [get_ports {done}]
  set_property IOSTANDARD LVCMOS18 [get_ports {clk}]
  set_property IOSTANDARD LVCMOS18 [get_ports {reset}]
  set_property IOSTANDARD LVCMOS18 [get_ports {go}]
  set_property IOSTANDARD LVCMOS18 [get_ports {done}]
  ```

  Use `mkTask3XilinxPnrReport`, copy the mapper summary/stat and P&R report
  into the final bundle, and embed a schema-version-1 manifest whose source is
  `tinystories-w8a8-via-linalg-no-handshake-il`, top is `main`, and target is
  `xc7k480tffg1156-1`. Export all four package names.

- [ ] **Step 4: Verify mapper and P&R evidence**

  Run in order, with no arbitrary cutoff:

  ```sh
  python3 -m unittest \
    tests.test_direct_linalg_xc7k480t_utilization.DirectLinalgXc7k480tUtilizationTest.test_root_flake_wires_full_w8a8_direct_linalg_xc7k480t_mapper_and_pnr \
    -v
  nix build .#tinystories-w8a8-via-linalg-no-handshake-xc7k480t-mapped-utilization \
    -L --no-link --print-out-paths
  nix build .#tinystories-w8a8-via-linalg-no-handshake-xc7k480t-nextpnr-utilization \
    -L --no-link --print-out-paths
  ```

  Read the immutable `summary.json`, `stat.json`, `route.json`, and logs. A
  mapper or router failure is a factual frontier, not a utilization result.

- [ ] **Step 5: Record only the actual P&R outcome and commit**

  Add immutable paths and mapped/P&R results to the full-model result document
  only if the corresponding artifacts exist. Keep the P&R probe limitation
  explicit: it is not a board-function or equivalence interface.

  ```sh
  git add flake.nix tests/test_direct_linalg_xc7k480t_utilization.py \
    docs/results/2026-07-15-full-w8a8-direct-linalg-scout.md
  git commit -m "feat: map full w8a8 direct linalg route"
  ```

## Final verification

After all applicable tasks, run:

```sh
python3 -m unittest tests.test_representative_core_no_handshake_sv -v
python3 -m unittest tests.test_calyx_preflight_report -v
python3 -m unittest tests.test_full_tinystories_w8a8_scout -v
nix flake check --no-build
git diff --check
git status --short
```

The only permitted remaining tracked working-tree change is the user-owned
`docs/glossary.md` modification.
