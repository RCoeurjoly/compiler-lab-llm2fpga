# Quantized RC Nonlinear Lowering Frontier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible, non-approximate evidence bundle that establishes which nonlinear families in the frozen PT2E W8A8 representative core can cross named upstream lowering routes, records the first remaining boundary when they cannot, and places that result beside a brief source-grounded survey of published FPGA nonlinear practice.

**Architecture:** Keep the frozen PT2E export and reference image unchanged. First make the Calyx wrapper reject error-bearing partial output, then derive provenance fragments from the actual Torch-MLIR and primitive scalar MRCs from the actual flat-SCF signatures. A short static survey classifies published polynomial, LUT, iterative, and model-level nonlinear techniques as possible future approximation families rather than routes already validated here. A Python runner records direct-Math, TOSA, and existing TOSA-compatibility route outcomes without treating a successful process exit as valid IR; a renderer turns that evidence into the bounded result document.

**Tech Stack:** Nix flakes, Python 3 standard library, Python `unittest`, Torch-MLIR, upstream MLIR TOSA/Math passes, CIRCT `--lower-scf-to-calyx`, checked-in MLIR pass plugin, and Git-tracked Markdown evidence.

## Global Constraints

- The unit under test remains exactly `tinystories-w8a8-rc-study-mask9-vocab6-width2`: static XNNPACK PT2E W8A8, vocabulary 6, two layers, context length 8, hidden width 2, one head, seed 0.
- The frozen PT2E reference image remains the numerical authority: four corpus inputs, six final raw int8 codes, output qparams, dequantized logits, and lowest-index argmax token ID.
- Do not modify the PyTorch model, calibration corpus, quantizer, exported program, model registry configuration, or reference image.
- Do not use `llm2fpga-lower-scout-math-for-calyx`, `1 + x` for exp, clamp for tanh, algebraic `fpowi` expansion, or any other approximation in an exactness, equivalence, working-system, or resource claim.
- Treat the actual source `math.rsqrt` as a provenance fact. `math.sqrt` is only the direct CIRCT supported-control MRC after the already-existing rsqrt-to-sqrt bridge; it is not evidence that the bridge is numerically equivalent.
- Run named upstream transformations exactly as installed by the pinned Nix inputs. Record the existing zero-point legalization separately as a local compatibility pass rather than calling it an upstream standard transformation.
- No generated SV, Yosys, DDR3, host software, board, bitstream, SmoothQuant, upstream issue, dependency update, or upstream patch work belongs in this implementation.
- The literature survey is descriptive and source-grounded only. It must not select an approximation, relax the frozen oracle, or convert a published hardware technique into an exactness claim.
- A route may be labelled `exact` only when it has a named implementation/specification, a valid output artifact, CIRCT acceptance where claimed, and a passing all-four-case raw-code-plus-token oracle comparison. This plan does not add a candidate execution path, so its initial matrix must not label any route exact.
- Preserve the existing dirty worktree. Stage and commit only files created or modified by the current task; do not use `git add -A`, destructive Git commands, `nix gc`, or durable `/tmp` artifacts.

---

## File structure

| File | Responsibility |
| --- | --- |
| `scripts/pipeline/scf_to_calyx_no_handshake.sh` | Reject CIRCT output whenever the lowerer emitted an error diagnostic, even if it wrote a non-empty partial file and returned zero. |
| `tests/test_scf_to_calyx_no_handshake.py` | Behavioral regression tests for accepted clean output and rejected error-bearing partial output. |
| `reproducers/calyx-math-exp/README.md` | Correct statement of the wrapper’s partial-output guard and pinned failure behavior. |
| `docs/results/2026-07-16-circt-scf-to-calyx-math-exp-status.md` | Issue-ready local evidence note; it does not claim an upstream report was filed. |
| `reproducers/calyx-math-tanh/input.mlir` | Scalar f32 `math.tanh` MRC matching the RC signature. |
| `reproducers/calyx-math-fpowi-cube/input.mlir` | Scalar f32, i64 constant-3 `math.fpowi` MRC matching the RC signature. |
| `reproducers/calyx-math-sqrt/input.mlir` | Scalar f32 `math.sqrt` CIRCT supported-control MRC. |
| `reproducers/calyx-math-*/README.md` | Scope, exact command, and non-equivalence contract for each primitive MRC. |
| `scripts/pipeline/extract_quantized_rc_nonlinear_slices.py` | Mechanically extracts non-executable Torch-MLIR provenance fragments and writes source SHA-256, ranges, and retained external values. |
| `tests/test_quantized_rc_nonlinear_slices.py` | Unit tests for source hashing, required family recognition, fragment provenance, and rejection of incomplete source input. |
| `docs/results/2026-07-16-fpga-transformer-nonlinear-practice-survey.md` | Brief, source-grounded survey of how published FPGA Transformer/LLM systems implement or reformulate nonlinear operations, explicitly distinguished from an exact PT2E route. |
| `tests/test_fpga_transformer_nonlinear_practice_survey.py` | Static contract test ensuring the survey retains its cited evidence map and frozen-oracle boundary. |
| `scripts/pipeline/run_quantized_rc_nonlinear_matrix.py` | Runs named primitive and whole-RC routes, captures logs/output validity, and emits the machine-readable evidence matrix. |
| `tests/test_quantized_rc_nonlinear_matrix.py` | Unit tests for error-diagnostic rejection, matrix schema, exactness gating, and oracle comparison schema. |
| `scripts/pipeline/render_quantized_rc_nonlinear_frontier.py` | Converts matrix and provenance evidence into deterministic JSON and Markdown conclusions. |
| `tests/test_quantized_rc_nonlinear_frontier_result.py` | Tests the bounded conclusion and ensures an approximation cannot be promoted to an exact route. |
| `flake.nix` | Builds the MRC suite and full RC evidence bundle as Nix outputs without making an expected compiler frontier a Nix build failure. |
| `tests/test_quantized_rc_nonlinear_frontier_nix.py` | Static Nix wiring contract for the evidence package, pinned tools, source artifacts, and result renderer. |
| `docs/results/2026-07-16-quantized-rc-nonlinear-lowering-frontier.md` | Git-tracked copy of the deterministic result Markdown generated from the completed evidence bundle. |
| `docs/results/2026-07-16-quantized-rc-working-system.md` | Corrects the source operation name to `math.rsqrt` and links to the bounded frontier result. |

## Evidence schema shared by Tasks 2, 4, and 5

The scripts added below use schema version 1. Keep these field names stable:

```json
{
  "schema_version": 1,
  "model_key": "tinystories-w8a8-rc-study-mask9-vocab6-width2",
  "source": {
    "path": "model.torch.mlir",
    "sha256": "<64 hexadecimal characters>",
    "stage": "torch-mlir"
  },
  "oracle": {
    "reference_sha256": "<64 hexadecimal characters>",
    "case_ids": ["ascending", "descending", "zeros", "alternating"],
    "comparison": {"status": "not-run", "reason": "no executable candidate"}
  },
  "route_documentation": {},
  "routes": [],
  "composites": []
}
```

`<64 hexadecimal characters>` is illustrative schema notation only; generated artifacts must contain actual SHA-256 values. The renderer must never reproduce this notation in a result claim.

### Task 1: Make the Calyx boundary reject error-bearing partial output and capture the upstream candidate

**Files:**

- Create: `tests/test_scf_to_calyx_no_handshake.py`
- Modify: `scripts/pipeline/scf_to_calyx_no_handshake.sh`
- Modify: `flake.nix`
- Modify: `reproducers/calyx-math-exp/README.md`
- Create: `docs/results/2026-07-16-circt-scf-to-calyx-math-exp-status.md`
- Modify: `tests/test_calyx_float_nix_package.py`

**Interfaces:**

- Consumes: `scf_to_calyx_no_handshake.sh <circt-opt> <input-flat-scf-mlir> <output-dir>`.
- Produces: `manifest.json` with `status`, `exit_code`, `diagnostic_error`, `partial_output_discarded`, `log`, and `normalized_input` on failure.
- Invariant: a Calyx artifact is accepted only when the subprocess exit code is zero, `model.calyx.mlir` is non-empty, and `lower-scf-to-calyx.log` has no MLIR diagnostic matching `(^|: )error:`.

- [ ] **Step 1: Write the failing wrapper regression tests**

  Create `tests/test_scf_to_calyx_no_handshake.py` with the following complete test harness. It uses a temporary fake `circt-opt`; it does not require CIRCT or Nix.

  ```python
  import json
  import subprocess
  import tempfile
  import unittest
  from pathlib import Path


  ROOT = Path(__file__).resolve().parents[1]
  SCRIPT = ROOT / "scripts" / "pipeline" / "scf_to_calyx_no_handshake.sh"


  class ScfToCalyxNoHandshakeTest(unittest.TestCase):
      def write_fake_circt(self, directory: Path, body: str) -> Path:
          tool = directory / "fake-circt-opt"
          tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
          tool.chmod(0o755)
          return tool

      def run_wrapper(self, tool_body: str) -> tuple[dict[str, object], Path]:
          tmp = tempfile.TemporaryDirectory()
          self.addCleanup(tmp.cleanup)
          root = Path(tmp.name)
          input_mlir = root / "input.mlir"
          output_dir = root / "out"
          input_mlir.write_text("module { func.func @main() { return } }\n", encoding="utf-8")
          tool = self.write_fake_circt(root, tool_body)
          result = subprocess.run(
              ["bash", str(SCRIPT), str(tool), str(input_mlir), str(output_dir)],
              check=False,
              capture_output=True,
              text=True,
          )
          self.assertEqual(result.returncode, 0, result.stderr)
          return json.loads((output_dir / "manifest.json").read_text(encoding="utf-8")), output_dir

      def test_rejects_zero_exit_error_diagnostic_and_partial_file(self) -> None:
          manifest, output_dir = self.run_wrapper(
              """
  output=""
  for ((index=1; index <= $#; index++)); do
    if [[ "${!index}" == "-o" ]]; then
      next=$((index + 1))
      output="${!next}"
    fi
  done
  printf 'error: Unhandled operation during BuildOpGroups()\\n' >&2
  printf 'calyx.component @partial() {}\\n' > "$output"
  exit 0
  """
          )

          self.assertEqual(manifest["status"], "failed")
          self.assertEqual(manifest["exit_code"], 0)
          self.assertTrue(manifest["diagnostic_error"])
          self.assertTrue(manifest["partial_output_discarded"])
          self.assertFalse((output_dir / "model.calyx.mlir").exists())
          self.assertIn("Unhandled operation", (output_dir / "lower-scf-to-calyx.log").read_text(encoding="utf-8"))

      def test_accepts_clean_zero_exit_nonempty_output(self) -> None:
          manifest, output_dir = self.run_wrapper(
              """
  output=""
  for ((index=1; index <= $#; index++)); do
    if [[ "${!index}" == "-o" ]]; then
      next=$((index + 1))
      output="${!next}"
    fi
  done
  printf 'calyx.component @main() {}\\n' > "$output"
  exit 0
  """
          )

          self.assertEqual(manifest, {"stage": "calyx", "status": "ok", "artifact": "model.calyx.mlir"})
          self.assertTrue((output_dir / "model.calyx.mlir").is_file())


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 2: Run the regression test and verify the current wrapper is RED**

  Run:

  ```sh
  python3 -m unittest tests.test_scf_to_calyx_no_handshake -v
  ```

  Expected: `test_rejects_zero_exit_error_diagnostic_and_partial_file` fails because the current manifest says `status: ok` and retains `model.calyx.mlir`.

- [ ] **Step 3: Implement diagnostic-aware acceptance**

  In `scripts/pipeline/scf_to_calyx_no_handshake.sh`, immediately after copying `$tmp_log` to `lower-scf-to-calyx.log`, insert this exact check and replace the current success condition with it:

  ```bash
  diagnostic_error=0
  if grep -Eq '(^|: )error:' "$tmp_log"; then
    diagnostic_error=1
  fi

  if [[ "$rc" -eq 0 && "$diagnostic_error" -eq 0 && -s "$output_dir/model.calyx.mlir" ]]; then
    cat >"$output_dir/manifest.json" <<'JSON'
  {"stage":"calyx","status":"ok","artifact":"model.calyx.mlir"}
  JSON
    exit 0
  fi

  partial_output_discarded=false
  if [[ -e "$output_dir/model.calyx.mlir" ]]; then
    partial_output_discarded=true
    rm -f "$output_dir/model.calyx.mlir"
  fi
  ```

  Replace the current failure-manifest Python program with this version so the failure is machine-readable even when the lowerer returns zero:

  ```bash
  python3 - "$output_dir/manifest.json" "$rc" "$diagnostic_error" "$partial_output_discarded" <<'PY'
  import json
  import sys
  from pathlib import Path

  Path(sys.argv[1]).write_text(
      json.dumps(
          {
              "stage": "calyx",
              "status": "failed",
              "exit_code": int(sys.argv[2]),
              "diagnostic_error": sys.argv[3] == "1",
              "partial_output_discarded": sys.argv[4] == "true",
              "reason": "lower-scf-to-calyx emitted an error diagnostic or did not produce a valid Calyx artifact",
              "log": "lower-scf-to-calyx.log",
              "normalized_input": "flat.scf.mlir",
          },
          sort_keys=True,
      )
      + "\n",
      encoding="utf-8",
  )
  PY
  ```

  Do not change the wrapper’s zero exit on a captured frontier. Its contract is to produce a completed diagnostic directory; downstream consumers decide from `manifest.json`.

- [ ] **Step 4: Run the wrapper regression test and verify GREEN**

  Run:

  ```sh
  python3 -m unittest tests.test_scf_to_calyx_no_handshake -v
  ```

  Expected: both tests pass. The clean fake lowerer is accepted; the zero-exit error fake lowerer is recorded as failed with no retained Calyx artifact.

- [ ] **Step 5: Freeze the pinned upstream observation in the Nix reproducer**

  In `flake.nix`, inside `calyxMathExpUpstreamReproducer`, add this line after `set -e` and before the diagnostic `grep` checks:

  ```nix
            test "$rc" -eq 0
  ```

  Add `"exit_code_observed": 0` to its `manifest.json`. In `tests/test_calyx_float_nix_package.py`, add assertions that the derivation contains `test "$rc" -eq 0`, writes `exit-code.txt`, writes `partial.calyx.mlir`, and writes `"valid_lowering": false`.

- [ ] **Step 6: Write the local upstream-candidate note**

  Create `docs/results/2026-07-16-circt-scf-to-calyx-math-exp-status.md` with these exact sections and facts:

  ```markdown
  # CIRCT SCF-to-Calyx `math.exp` Diagnostic-Status Candidate

  ## Scope

  This note records a local, issue-ready observation. No upstream issue or patch
  has been filed from this repository.

  ## Revisions inspected

  - Pinned CIRCT: `5dc62fe46c9dbf8936f4f706083301e7503715eb` (`2026-03-31`).
  - Upstream main inspected: `ffd2188ab345cdaf655ebcec348d9635bedd0f3e`
    (`2026-07-16`).
  - Result of source inspection: `math::ExpOp` remains absent from the
    SCF-to-Calyx supported-operation handling; the post-pin SCF-to-Calyx change
    was tracking-safe mutation refactoring, not this failure-status behavior.

  ## Minimal command

  ```sh
  /nix/store/6nz8q4n4z2c3yb6xikq84rbn1rrh61xy-circt-1.144.0g20260331_5dc62fe/bin/circt-opt \
    reproducers/calyx-math-exp/input.mlir \
    --lower-scf-to-calyx='top-level-function=main' \
    -o /dev/null
  ```

  ## Expected and observed behavior

  Expected: an error diagnostic causes a nonzero process status and no caller
  accepts partial Calyx text as a valid lowering.

  Observed: CIRCT prints `error: Unhandled operation during BuildOpGroups()`
  naming `math.exp`, writes partial Calyx text when given an output path, and
  returns status zero.

  The full RC also reaches a later verifier error and is recorded locally as a
  failed Calyx stage. That later error does not repair the direct minimal-case
  status defect.

  ## Issue-ready report

  Title: `SCF-to-Calyx reports an unhandled math.exp error but exits zero and
  writes partial output`.

  Attach `reproducers/calyx-math-exp/input.mlir`, the exact command above,
  `lower.log`, `exit-code.txt`, and `partial.calyx.mlir` from
  `calyx-math-exp-upstream-reproducer`.
  ```

  Keep the source revisions and the direct command exactly as shown. Do not state that upstream has acknowledged the report.

- [ ] **Step 7: Align the MRC README and Nix contract test with the diagnostic-status boundary**

  In `reproducers/calyx-math-exp/README.md`, replace the paragraph beginning `Current CIRCT may still print` with this exact paragraph:

  ```markdown
  Current CIRCT may print a partial Calyx module after this diagnostic and still
  return exit status zero. That output is not a valid lowered artifact. The
  repository wrapper accepts Calyx only when the lowerer returns zero, writes a
  non-empty artifact, and emits no MLIR `error:` diagnostic; otherwise it
  discards the partial file and records a failed manifest.
  ```

  Add this complete method to `tests/test_calyx_float_nix_package.py` before the module-level `if __name__` block:

  ```python
      def test_math_exp_reproducer_records_zero_exit_as_invalid_lowering(self) -> None:
          fixture = ROOT / "reproducers" / "calyx-math-exp" / "input.mlir"
          readme = ROOT / "reproducers" / "calyx-math-exp" / "README.md"
          flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
          self.assertTrue(fixture.exists())
          self.assertIn("math.exp", fixture.read_text(encoding="utf-8"))
          self.assertIn("emits no MLIR `error:` diagnostic", readme.read_text(encoding="utf-8"))
          self.assertIn('calyxMathExpUpstreamReproducer = pkgs.runCommand', flake)
          self.assertIn('test "$rc" -eq 0', flake)
          self.assertIn('printf \'%s\\n\' "$rc" >"$out/exit-code.txt"', flake)
          self.assertIn('"valid_lowering": false', flake)
          self.assertIn('"exit_code_observed": 0', flake)
  ```

- [ ] **Step 8: Verify the pinned MRC and all Task 1 tests**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_scf_to_calyx_no_handshake \
    tests.test_calyx_float_nix_package \
    -v
  nix build .#calyx-math-exp-upstream-reproducer -L --no-link --print-out-paths
  ```

  Expected: Python tests pass. The Nix output contains `exit-code.txt` containing `0`, a non-empty `partial.calyx.mlir`, a diagnostic naming `math.exp`, and a manifest with `valid_lowering: false`.

- [ ] **Step 9: Commit Task 1 only**

  ```sh
  git add scripts/pipeline/scf_to_calyx_no_handshake.sh \
    tests/test_scf_to_calyx_no_handshake.py \
    tests/test_calyx_float_nix_package.py \
    flake.nix \
    reproducers/calyx-math-exp/README.md \
    docs/results/2026-07-16-circt-scf-to-calyx-math-exp-status.md
  git commit -m "fix: reject error-bearing Calyx partial output"
  ```

### Task 2: Add exact primitive MRCs and mechanically derived composite provenance fragments

**Files:**

- Create: `reproducers/calyx-math-tanh/input.mlir`
- Create: `reproducers/calyx-math-tanh/README.md`
- Create: `reproducers/calyx-math-fpowi-cube/input.mlir`
- Create: `reproducers/calyx-math-fpowi-cube/README.md`
- Create: `reproducers/calyx-math-sqrt/input.mlir`
- Create: `reproducers/calyx-math-sqrt/README.md`
- Modify: `reproducers/calyx-math-rsqrt/README.md`
- Create: `scripts/pipeline/extract_quantized_rc_nonlinear_slices.py`
- Create: `tests/test_quantized_rc_nonlinear_slices.py`

**Interfaces:**

- Consumes: one Torch-MLIR text file and one flat-SCF MLIR text file from the frozen RC.
- Produces: `slices.json`, `primitive-observations.json`, and `slices/*.mlirfrag`.
- Invariant: `.mlirfrag` files are provenance fragments, explicitly non-executable, and never advertised as independently equivalent models.

- [ ] **Step 1: Write failing tests for primitive signatures and extraction metadata**

  Create `tests/test_quantized_rc_nonlinear_slices.py`. Use the following source fixture and assertions; it is deliberately small and is only a parser test, not RC evidence.

  ```python
  import hashlib
  import json
  import subprocess
  import sys
  import tempfile
  import unittest
  from pathlib import Path


  ROOT = Path(__file__).resolve().parents[1]
  EXTRACT = ROOT / "scripts" / "pipeline" / "extract_quantized_rc_nonlinear_slices.py"

  TORCH_SOURCE = """module {
    func.func @main(%arg0: !torch.vtensor<[1,8,2],si8>) {
      %c3 = torch.constant.int 3
      %dq0 = torch.aten.dequantize.tensor %arg0 : !torch.vtensor<[1,8,2],!torch.qint8> -> !torch.vtensor<[1,8,2],f32>
      %max = torch.aten.max.dim %dq0, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.int, !torch.bool -> !torch.vtensor<[1,8,1],f32>, !torch.vtensor<[1,8,1],si64>
      %sub = torch.aten.sub.Tensor %dq0, %max, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.vtensor<[1,8,1],f32>, !torch.float -> !torch.vtensor<[1,8,2],f32>
      %exp = torch.aten.exp %sub : !torch.vtensor<[1,8,2],f32> -> !torch.vtensor<[1,8,2],f32>
      %sum = torch.aten.sum.dim_IntList %exp, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.list<int>, !torch.bool, !torch.none -> !torch.vtensor<[1,8,1],f32>
      %softmax = torch.aten.div.Tensor %exp, %sum : !torch.vtensor<[1,8,2],f32>, !torch.vtensor<[1,8,1],f32> -> !torch.vtensor<[1,8,2],f32>
      %pow = torch.aten.pow.Tensor_Scalar %dq0, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.int -> !torch.vtensor<[1,8,2],f32>
      %tanh = torch.aten.tanh %pow : !torch.vtensor<[1,8,2],f32> -> !torch.vtensor<[1,8,2],f32>
      %gelu_q = torch.aten.quantize_per_tensor %tanh, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.float, !torch.int, !torch.dtype -> !torch.vtensor<[1,8,2],!torch.qint8>
      %mean = torch.aten.sum.dim_IntList %dq0, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.list<int>, !torch.bool, !torch.none -> !torch.vtensor<[1,8,1],f32>
      %div = torch.aten.div.Scalar %mean, %c3 : !torch.vtensor<[1,8,1],f32>, !torch.float -> !torch.vtensor<[1,8,1],f32>
      %add = torch.aten.add.Scalar %div, %c3, %c3 : !torch.vtensor<[1,8,1],f32>, !torch.float, !torch.float -> !torch.vtensor<[1,8,1],f32>
      %rsqrt = torch.aten.rsqrt %add : !torch.vtensor<[1,8,1],f32> -> !torch.vtensor<[1,8,1],f32>
      %broadcast = torch.aten.broadcast_to %rsqrt, %c3 : !torch.vtensor<[1,8,1],f32>, !torch.list<int> -> !torch.vtensor<[1,8,2],f32>
      %layernorm_q = torch.aten.quantize_per_tensor %broadcast, %c3, %c3, %c3 : !torch.vtensor<[1,8,2],f32>, !torch.float, !torch.int, !torch.dtype -> !torch.vtensor<[1,8,2],!torch.qint8>
      return
    }
  }
  """

  FLAT_SCF_SOURCE = """module {
    func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
      %value = memref.load %input[%c0] : memref<1xf32>
      %exp = math.exp %value : f32
      %pow = math.fpowi %value, %c3_i64 : f32, i64
      %tanh = math.tanh %value : f32
      %rsqrt = math.rsqrt %value : f32
      memref.store %exp, %output[%c0] : memref<1xf32>
      return
    }
  }
  """

  class QuantizedRcNonlinearSlicesTest(unittest.TestCase):
      def run_extract(self, torch_source: str = TORCH_SOURCE) -> tuple[dict, dict, Path]:
          tmp = tempfile.TemporaryDirectory()
          self.addCleanup(tmp.cleanup)
          root = Path(tmp.name)
          torch_path = root / "model.torch.mlir"
          flat_path = root / "flat.scf.mlir"
          out = root / "out"
          torch_path.write_text(torch_source, encoding="utf-8")
          flat_path.write_text(FLAT_SCF_SOURCE, encoding="utf-8")
          result = subprocess.run(
              [
                  sys.executable, str(EXTRACT),
                  "--torch-mlir", str(torch_path),
                  "--flat-scf", str(flat_path),
                  "--model-key", "tinystories-w8a8-rc-study-mask9-vocab6-width2",
                  "--out-dir", str(out),
              ],
              check=False, capture_output=True, text=True,
          )
          self.assertEqual(result.returncode, 0, result.stderr)
          return (
              json.loads((out / "slices.json").read_text(encoding="utf-8")),
              json.loads((out / "primitive-observations.json").read_text(encoding="utf-8")),
              out,
          )

      def test_preserves_source_hash_family_ranges_and_external_values(self) -> None:
          slices, primitive, out = self.run_extract()

          self.assertEqual(slices["source"]["sha256"], hashlib.sha256(TORCH_SOURCE.encode()).hexdigest())
          self.assertEqual({entry["family"] for entry in slices["composites"]}, {"attention-softmax", "tanh-gelu", "layernorm"})
          self.assertEqual(primitive["op_counts"], {"math.exp": 1, "math.fpowi": 1, "math.rsqrt": 1, "math.tanh": 1})
          for entry in slices["composites"]:
              fragment = out / entry["fragment"]
              self.assertTrue(fragment.is_file())
              text = fragment.read_text(encoding="utf-8")
              self.assertIn("non-executable provenance fragment", text)
              self.assertIn("source_sha256:", text)
              self.assertTrue(entry["retained_external_values"])
              self.assertGreaterEqual(entry["source_range"][0], 1)

      def test_rejects_source_without_all_required_families(self) -> None:
          with self.assertRaises(AssertionError):
              self.run_extract(TORCH_SOURCE.replace("torch.aten.tanh", "torch.aten.sin"))


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 2: Run the tests and verify RED**

  Run:

  ```sh
  python3 -m unittest tests.test_quantized_rc_nonlinear_slices -v
  ```

  Expected: import/execution failure because the extraction script and primitive files do not yet exist.

- [ ] **Step 3: Add the three primitive MRCs**

  Create `reproducers/calyx-math-tanh/input.mlir` exactly as:

  ```mlir
  module {
    func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
      %c0 = arith.constant 0 : index
      %value = memref.load %input[%c0] : memref<1xf32>
      %result = math.tanh %value : f32
      memref.store %result, %output[%c0] : memref<1xf32>
      return
    }
  }
  ```

  Create `reproducers/calyx-math-fpowi-cube/input.mlir` exactly as:

  ```mlir
  module {
    func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
      %c0 = arith.constant 0 : index
      %c3_i64 = arith.constant 3 : i64
      %value = memref.load %input[%c0] : memref<1xf32>
      %result = math.fpowi %value, %c3_i64 : f32, i64
      memref.store %result, %output[%c0] : memref<1xf32>
      return
    }
  }
  ```

  Create `reproducers/calyx-math-sqrt/input.mlir` exactly as:

  ```mlir
  module {
    func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
      %c0 = arith.constant 0 : index
      %value = memref.load %input[%c0] : memref<1xf32>
      %result = math.sqrt %value : f32
      memref.store %result, %output[%c0] : memref<1xf32>
      return
    }
  }
  ```

  Each new README must contain all of these statements, substituting only the operation name and exact file path:

  ```markdown
  This MRC preserves the scalar signature observed in the frozen W8A8 RC.

  ```sh
  circt-opt input.mlir --lower-scf-to-calyx='top-level-function=main'
  ```

  It is a compiler-capability probe, not numerical-equivalence evidence.
  Textual MLIR substitution and the resource-scout nonlinear pass are not acceptable fixes.
  ```

  In the `math.fpowi` README, state explicitly that exponent `3 : i64` was observed in the RC and that algebraic strength reduction is not asserted exact. In the `math.sqrt` README, state that this is the supported-control operation, not a proof that `math.rsqrt -> 1 / math.sqrt` preserves PT2E results.

- [ ] **Step 4: Correct the existing rsqrt MRC’s scope**

  Replace the claim in `reproducers/calyx-math-rsqrt/README.md` that rsqrt is the current blocker with this factual text:

  ```markdown
  The frozen RC source contains scalar `math.rsqrt` in its LayerNorm-like paths.
  The active pre-Calyx helper currently rewrites this source form to `1.0 /
  math.sqrt`; the separate `calyx-math-sqrt` MRC verifies only that current
  CIRCT accepts the resulting `math.sqrt` primitive. Neither fact is a
  raw-code equivalence result for the rewrite.
  ```

  Retain the original raw `math.rsqrt` input file because it documents the actual source signature.

- [ ] **Step 5: Implement deterministic extraction**

  Create `scripts/pipeline/extract_quantized_rc_nonlinear_slices.py` with these public constants and data records:

  ```python
  RESULT_RE = re.compile(r"^\\s*(?P<results>%[-A-Za-z0-9_.$]+(?:\\s*,\\s*%[-A-Za-z0-9_.$]+)*)\\s*=\\s*(?P<op>[A-Za-z_][-A-Za-z0-9_.$]*(?:\\.[-A-Za-z0-9_.$]+)*)")
  SSA_RE = re.compile(r"%[-A-Za-z0-9_.$]+")

  REQUIRED_FAMILIES = {
      "attention-softmax": ("torch.aten.exp", "torch.aten.max.dim", "torch.aten.sub.Tensor", "torch.aten.sum.dim_IntList", "torch.aten.div.Tensor"),
      "tanh-gelu": ("torch.aten.pow.Tensor_Scalar", "torch.aten.tanh"),
      "layernorm": ("torch.aten.rsqrt", "torch.aten.sum.dim_IntList", "torch.aten.div.Scalar"),
  }

  @dataclass(frozen=True)
  class Operation:
      line_number: int
      text: str
      results: list[str]
      op: str
      operands: list[str]


  @dataclass(frozen=True)
  class Slice:
      family: str
      occurrence: int
      anchor_operation: str
      first_line: int
      last_line: int
      lines: list[str]
      retained_external_values: list[str]
  ```

  Export `sha256(path: Path) -> str`, `parse_operations(lines: list[str]) -> list[Operation]`, `extract_family(lines: list[str], operations: list[Operation], family: str) -> list[Slice]`, `write_fragment(path: Path, source_sha256: str, slice_: Slice) -> None`, and `count_flat_scf_nonlinears(text: str) -> dict[str, int]`. Their complete required behaviour is specified by the seven rules below; use the `Operation` and `Slice` records exactly as declared above.

  Implement the following exact extraction rules:

  1. Locate every anchor op for a family in source order.
  2. For `attention-softmax`, require a `max.dim`, `sub.Tensor`, `exp`, `sum.dim_IntList`, and `div.Tensor` chain in a contiguous forward region where each result is consumed by the next semantic operation. The fragment begins at the nearest preceding `torch.aten.dequantize.tensor` and ends at the `div.Tensor` result.
  3. For `tanh-gelu`, require a preceding `pow.Tensor_Scalar` with an integer constant operand and a subsequent `tanh` before the next LayerNorm `rsqrt`. The fragment begins at the nearest preceding dequantize and ends at the first quantize after the tanh.
  4. For `layernorm`, require a `sum.dim_IntList`, `div.Scalar`, `add.Scalar`, `rsqrt`, and following `broadcast_to` chain. The fragment begins at the nearest preceding dequantize and ends at the first quantize after that broadcast.
  5. A retained external value is an SSA value used in the fragment but not defined inside it. Sort and record these values. Do not invent definitions for them.
  6. Write each fragment as `slices/<family>-<occurrence>.mlirfrag` with comment-only metadata preceding the original source lines:

     ```mlir
     // GENERATED: non-executable provenance fragment; not a semantic replacement.
     // source_sha256: <actual hash>
     // source_range: <first>-<last>
     // family: <family>
     // retained_external_values: %a, %b
     ```

  7. If any required family is absent, raise `ValueError("missing required nonlinear family: <family>")`. If `math.exp`, `math.fpowi`, `math.tanh`, or `math.rsqrt` is absent from flat-SCF, raise `ValueError` naming the missing operation.

  `main()` must accept exactly these arguments:

  ```text
  --torch-mlir PATH --flat-scf PATH --model-key STRING --out-dir PATH
  ```

  It writes `slices.json` and `primitive-observations.json` under `--out-dir`. `slices.json` contains `schema_version`, `model_key`, source path/hash/stage, and every fragment’s family, anchor operation, source range, retained external values, fragment path, `executable: false`, and `semantic_replacement: false`.

- [ ] **Step 6: Verify the extraction tests are GREEN**

  Run:

  ```sh
  python3 -m unittest tests.test_quantized_rc_nonlinear_slices -v
  ```

  Expected: both tests pass. The emitted fixture fragments contain source hash/range metadata and explicitly say they are non-executable provenance fragments.

- [ ] **Step 7: Commit Task 2 only**

  ```sh
  git add reproducers/calyx-math-tanh \
    reproducers/calyx-math-fpowi-cube \
    reproducers/calyx-math-sqrt \
    reproducers/calyx-math-rsqrt/README.md \
    scripts/pipeline/extract_quantized_rc_nonlinear_slices.py \
    tests/test_quantized_rc_nonlinear_slices.py
  git commit -m "test: capture quantized RC nonlinear provenance"
  ```

### Task 3: Publish a bounded survey of FPGA Transformer nonlinear practice

**Files:**

- Create: `docs/results/2026-07-16-fpga-transformer-nonlinear-practice-survey.md`
- Create: `tests/test_fpga_transformer_nonlinear_practice_survey.py`

**Interfaces:**

- Consumes: the five primary-paper URLs listed in Step 3 and the frozen-oracle constraints from this plan.
- Produces: a short Markdown evidence map that distinguishes direct operator preservation from approximation, lookup-table implementation, iterative arithmetic, and model-level reformulation.
- Invariant: the survey may justify a future, separately evaluated approximation study; it must not recast any practical approximation as a bit-exact or already approved PT2E lowering route.

- [ ] **Step 1: Write the failing survey-contract test**

  Create `tests/test_fpga_transformer_nonlinear_practice_survey.py` with this complete test:

  ```python
  import unittest
  from pathlib import Path


  ROOT = Path(__file__).resolve().parents[1]
  SURVEY = ROOT / "docs" / "results" / "2026-07-16-fpga-transformer-nonlinear-practice-survey.md"


  class FpgaTransformerNonlinearPracticeSurveyTest(unittest.TestCase):
      def test_survey_has_primary_sources_and_preserves_the_oracle_boundary(self) -> None:
          text = SURVEY.read_text(encoding="utf-8")
          for url in (
              "https://proceedings.mlr.press/v139/kim21d.html",
              "https://dai.sjtu.edu.cn/my_file/pdf/4fcb20f6-7386-4907-a138-bb24e21d2260.pdf",
              "https://iris.polito.it/retrieve/handle/11583/2987506/cd452780-3ae7-457f-9349-d980c79d0ac7/2304.03986.pdf",
              "https://www.mdpi.com/2079-9292/14/12/2337",
              "https://www.mdpi.com/2072-666X/17/1/84",
          ):
              self.assertIn(url, text)
          for heading in (
              "## Scope and finding",
              "## Evidence map",
              "## What this does and does not authorize",
          ):
              self.assertIn(heading, text)
          for operation in ("math.exp", "math.tanh", "math.fpowi", "math.rsqrt"):
              self.assertIn(operation, text)
          self.assertIn("approximation or reformulation", text)
          self.assertIn("does not authorize changing the frozen PT2E W8A8 oracle", text)
          self.assertIn("not a semantic-equivalence proof", text)


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 2: Run the survey-contract test and verify RED**

  Run:

  ```sh
  python3 -m unittest tests.test_fpga_transformer_nonlinear_practice_survey -v
  ```

  Expected: failure because the survey document does not yet exist.

- [ ] **Step 3: Write the source-grounded survey without making a design selection**

  Create `docs/results/2026-07-16-fpga-transformer-nonlinear-practice-survey.md` with exactly this content. Keep the wording bounded to the cited sources; do not add a claim about a paper's numerical method unless its primary paper describes it.

  ```markdown
  # FPGA Transformer Nonlinear Practice Survey

  **Question.** How do published Transformer/LLM accelerators deal with the nonlinear operations that remain in the frozen PT2E W8A8 representative core: `math.exp`, `math.tanh`, `math.fpowi`, and `math.rsqrt`?

  ## Scope and finding

  This is a brief implementation-practice survey, not a performance comparison and not a claim that any cited method preserves this repository's frozen PT2E W8A8 semantics. Across the sources below, Softmax exponentials, GELU-like activations, and normalization roots are normally handled by approximation or reformulation: range reduction plus polynomial or piecewise-linear arithmetic, lookup tables, iterative root arithmetic, or a dedicated special-function block. The sources do not establish a bit-exact route for the RC's PyTorch `math.exp`, `math.tanh`, `math.fpowi`, or `math.rsqrt` operations through their original Q/DQ-wrapped floating-point semantics.

  The last sentence is an inference from the cited papers' stated implementation scopes, not a claim that no such implementation exists anywhere.

  ## Evidence map

  | Source | Hardware context | `exp` / Softmax | GELU, `tanh`, or `pow` | `sqrt` / `rsqrt` / normalization | Interpretation for this RC |
  | --- | --- | --- | --- | --- |
  | [I-BERT](https://proceedings.mlr.press/v139/kim21d.html) | Integer-only BERT quantization; not an FPGA implementation | Replaces Softmax with an integer-only approximation | Replaces GELU with an integer-only approximation; it is not a direct `math.tanh` or `math.fpowi` preservation result | Replaces LayerNorm with an integer-only approximation | A widely cited model-level precedent for reformulating nonlinear layers before hardware lowering, but not proof of equivalence to this frozen PT2E export. |
  | [FlightLLM](https://dai.sjtu.edu.cn/my_file/pdf/4fcb20f6-7386-4907-a138-bb24e21d2260.pdf) | FPGA LLM system | Assigns Softmax to its MISC instruction class; the paper lists Softmax lookup tables among small single-access data stored in DDR | The same MISC/LUT treatment includes GELU and SiLU; the paper does not present this as a direct primitive `tanh` or `pow` implementation | Assigns LayerNorm to MISC | Architectural precedent for an explicit special-function/LUT subsystem, not a numerical specification for this RC. |
  | [SwiftTron](https://iris.polito.it/retrieve/handle/11583/2987506/cd452780-3ae7-457f-9349-d980c79d0ac7/2304.03986.pdf) | Transformer accelerator; ASIC rather than FPGA | Subtracts the maximum, range-reduces the exponential input to `[-ln(2), 0]`, then uses a second-order polynomial | Approximates GELU's `erf` component with a second-order polynomial; this is a GELU reformulation rather than direct `math.tanh` or `math.fpowi` preservation | Uses an iterative square-root algorithm for LayerNorm | A detailed architectural precedent for polynomial/iterative nonlinear units, but its ASIC setting and approximation choice are not an approved FPGA compiler route. |
  | [Approximation-Based Softmax and LayerNorm Accelerator](https://www.mdpi.com/2079-9292/14/12/2337) | FPGA VU37P; BERT and GPT-2 | Uses piecewise-linear exponential approximation in Softmax | Does not establish a direct `tanh` or `pow` primitive route | Uses Newton-Raphson square-root approximation in LayerNorm | Direct FPGA evidence that approximation is practical, together with the paper's caution that generation can be more sensitive than classification. |
  | [Hardware-Oriented Approximations of Softmax and RMSNorm](https://www.mdpi.com/2072-666X/17/1/84) | FPGA U55C; LLaMA2-7B | Uses range reduction, bipartite lookup tables, and log-domain division for Softmax | Does not establish a direct `tanh` or `pow` primitive route | Uses leading-one detection, lookup tables, and multiplication for reciprocal square root in RMSNorm | Recent FPGA/LLM precedent for fixed-point Softmax and reciprocal-root approximation, not a bit-exact implementation of `math.rsqrt`. |

  ## Cross-paper reading by source operation

  - `math.exp`: published hardware work usually first reduces its input range, then uses a polynomial, piecewise-linear approximation, or lookup table. It is commonly embedded inside a complete Softmax dataflow that also performs maximum subtraction and normalization.
  - `math.rsqrt`: LayerNorm or RMSNorm is generally treated as a compound operation. Papers use iterative square-root arithmetic or a leading-one-detection/LUT/multiply reciprocal-root datapath rather than retain a general floating `math.rsqrt` operation.
  - `math.tanh` and `math.fpowi`: this small source set does not document a direct primitive implementation matching PyTorch's operations. In practice the surrounding GELU is reformulated or table/polynomial approximated, so the important comparison is the full activation's numerical behaviour, not local textual replacement of either primitive.

  ## What this does and does not authorize

  This survey makes a future approximation or reformulation study defensible: it gives concrete, published families of alternatives to investigate after the standard-route frontier is measured. It does not authorize changing the frozen PT2E W8A8 oracle, silently rewriting an operation in the current route, or calling a LUT/polynomial/iterative design exact.

  Any candidate based on these techniques needs its own declared numerical contract and all-four-corpus-case comparison of six raw int8 output codes plus the token ID against the frozen reference. Until that comparison passes under an explicitly approved tolerance or exactness policy, the technique is not a semantic-equivalence proof.
  ```

- [ ] **Step 4: Verify the survey-contract test is GREEN**

  Run:

  ```sh
  python3 -m unittest tests.test_fpga_transformer_nonlinear_practice_survey -v
  ```

  Expected: pass. The document has all five direct primary-source links, names every source operation, and states that the survey does not alter the oracle or prove equivalence.

- [ ] **Step 5: Commit Task 3 only**

  ```sh
  git add docs/results/2026-07-16-fpga-transformer-nonlinear-practice-survey.md \
    tests/test_fpga_transformer_nonlinear_practice_survey.py
  git commit -m "docs: survey FPGA nonlinear practice"
  ```

### Task 4: Build the standard-route evidence matrix and protect the exactness claim

**Files:**

- Create: `scripts/pipeline/run_quantized_rc_nonlinear_matrix.py`
- Create: `tests/test_quantized_rc_nonlinear_matrix.py`

**Interfaces:**

- Consumes: primitive MRC paths, frozen RC Torch-MLIR, frozen RC flat-SCF, provenance `slices.json`, reference `reference.json`, and paths to pinned executables.
- Produces: `matrix.json`, per-command logs and outputs under `commands/`, and `oracle-comparison.json`.
- Invariant: a command with a zero exit and an `error:` diagnostic is `rejected`; a route is never `exact` without all-four-case raw-code/token comparison status `pass`.

- [ ] **Step 1: Write failing tests for command classification and claim validation**

  Create `tests/test_quantized_rc_nonlinear_matrix.py` with the following core tests. Import the script by file path so its pure functions are testable without Nix.

  ```python
  import importlib.util
  import json
  import os
  import tempfile
  import unittest
  from pathlib import Path


  ROOT = Path(__file__).resolve().parents[1]
  SCRIPT = ROOT / "scripts" / "pipeline" / "run_quantized_rc_nonlinear_matrix.py"


  def load_module():
      spec = importlib.util.spec_from_file_location("nonlinear_matrix", SCRIPT)
      assert spec is not None and spec.loader is not None
      module = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(module)
      return module


  class QuantizedRcNonlinearMatrixTest(unittest.TestCase):
      def test_error_diagnostic_overrides_zero_exit_and_output_file(self) -> None:
          module = load_module()
          with tempfile.TemporaryDirectory() as tmp:
              root = Path(tmp)
              tool = root / "tool"
              output = root / "out.mlir"
              log = root / "tool.log"
              tool.write_text(
                  "#!/usr/bin/env bash\nprintf 'error: unsupported op\\n' >&2\nprintf 'partial\\n' > \"$2\"\nexit 0\n",
                  encoding="utf-8",
              )
              tool.chmod(0o755)
              attempt = module.run_command("fake", [str(tool), "-o", str(output)], log, output)

          self.assertEqual(attempt["status"], "rejected")
          self.assertEqual(attempt["exit_code"], 0)
          self.assertTrue(attempt["diagnostic_error"])
          self.assertTrue(attempt["output_exists"])

      def test_exact_claim_requires_passing_raw_code_and_token_comparison(self) -> None:
          module = load_module()
          row = {
              "route_id": "direct-math-to-funcs",
              "semantic_classification": "exact",
              "oracle_comparison": {"status": "not-run"},
          }
          with self.assertRaisesRegex(ValueError, "oracle comparison"):
              module.validate_semantic_claim(row)

      def test_scout_or_approximate_route_cannot_be_exact(self) -> None:
          module = load_module()
          row = {
              "route_id": "scout-exp-approximation",
              "semantic_classification": "exact",
              "oracle_comparison": {"status": "pass"},
          }
          with self.assertRaisesRegex(ValueError, "approximate or scout"):
              module.validate_semantic_claim(row)

      def test_route_documentation_distinguishes_upstream_and_local_steps(self) -> None:
          module = load_module()
          self.assertEqual(
              module.ROUTE_DOCUMENTATION["mlir-tosa"]["kind"],
              "upstream-specification-and-tool",
          )
          self.assertEqual(
              module.ROUTE_DOCUMENTATION["llm2fpga-zero-point-compatibility"]["kind"],
              "repository-local-pass",
          )
          self.assertIn(
              "LegalizePt2eTosaZeroPoint.cpp",
              module.ROUTE_DOCUMENTATION["llm2fpga-zero-point-compatibility"]["reference"],
          )

      def test_oracle_comparison_requires_six_codes_and_token_per_case(self) -> None:
          module = load_module()
          reference = {
              "results": [
                  {"case_id": "ascending", "output_codes_i8": [1, 2, 3, 4, 5, 6], "token_id": 2}
              ]
          }
          candidate = {
              "results": [
                  {"case_id": "ascending", "output_codes_i8": [1, 2, 3, 4, 5, 6], "token_id": 2}
              ]
          }
          self.assertEqual(module.compare_oracle(reference, candidate)["status"], "pass")
          candidate["results"][0]["output_codes_i8"][5] = 7
          self.assertEqual(module.compare_oracle(reference, candidate)["status"], "fail")


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 2: Run the tests and verify RED**

  Run:

  ```sh
  python3 -m unittest tests.test_quantized_rc_nonlinear_matrix -v
  ```

  Expected: import failure because `run_quantized_rc_nonlinear_matrix.py` does not exist.

- [ ] **Step 3: Implement the command-result primitive**

  In `scripts/pipeline/run_quantized_rc_nonlinear_matrix.py`, define these exact public functions before `main()`:

  ```python
  ERROR_RE = re.compile(r"(^|: )error:", re.MULTILINE)
  FLOAT_OP_RE = re.compile(r"\\b(?:math\\.[A-Za-z0-9_]+|arith\\.[A-Za-z0-9_]*f[A-Za-z0-9_]*)\\b")
  INTEGER_TOSA_RE = re.compile(r"\\btosa\\.(?:table|rescale|apply_rescale)\\b")

  def run_command(label: str, command: list[str], log_path: Path, output_path: Path | None) -> dict[str, object]:
      completed = subprocess.run(command, check=False, capture_output=True, text=True)
      log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
      diagnostic_error = bool(ERROR_RE.search(completed.stdout + completed.stderr))
      output_exists = output_path is not None and output_path.is_file() and output_path.stat().st_size > 0
      return {
          "label": label,
          "command": command,
          "exit_code": completed.returncode,
          "diagnostic_error": diagnostic_error,
          "output_exists": output_exists,
          "status": "accepted" if completed.returncode == 0 and not diagnostic_error and output_exists else "rejected",
          "log": str(log_path.name),
          "output": None if output_path is None else str(output_path.name),
      }

  def compare_oracle(reference: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
      expected = {row["case_id"]: row for row in reference["results"]}
      observed = {row["case_id"]: row for row in candidate["results"]}
      cases = []
      for case_id in sorted(expected):
          lhs = expected[case_id]
          rhs = observed.get(case_id)
          codes_match = rhs is not None and lhs["output_codes_i8"] == rhs.get("output_codes_i8")
          token_match = rhs is not None and lhs["token_id"] == rhs.get("token_id")
          cases.append({"case_id": case_id, "codes_match": codes_match, "token_match": token_match})
      return {"status": "pass" if cases and all(row["codes_match"] and row["token_match"] for row in cases) else "fail", "cases": cases}

  def validate_semantic_claim(row: dict[str, object]) -> None:
      if row["semantic_classification"] != "exact":
          return
      route_id = str(row["route_id"]).lower()
      if "scout" in route_id or "approx" in route_id:
          raise ValueError("approximate or scout route cannot be exact")
      if row["oracle_comparison"]["status"] != "pass":
          raise ValueError("exact route requires a passing oracle comparison")
  ```

  The actual source must include imports for `argparse`, `hashlib`, `json`, `re`, `subprocess`, `Path`, and `Any`. Serialize every JSON file with `json.dumps(payload, indent=2, sort_keys=True)` where `payload` is the object being written.

- [ ] **Step 4: Implement the primitive matrix without an approximation path**

  Add `run_primitive_routes()` that takes `{name: Path}` and emits these route IDs for every primitive MRC:

  ```text
  direct-circt
  upstream-canonicalize-cse
  upstream-convert-math-to-funcs
  upstream-convert-math-to-libm
  ```

  Use these exact command forms, always creating an output and log path under `commands/<primitive>/<route-id>/`:

  ```python
  [circt_opt, str(input_mlir), "--lower-scf-to-calyx=top-level-function=main", "-o", str(calyx_output)]
  [mlir_opt, str(input_mlir), "--canonicalize", "--cse", "-o", str(normalized_output)]
  [mlir_opt, str(input_mlir), "--convert-math-to-funcs", "-o", str(function_output)]
  [mlir_opt, str(input_mlir), "--convert-math-to-libm", "-o", str(libm_output)]
  ```

  For each transformed MLIR output that is accepted, invoke the same direct CIRCT command on it and record its result as `calyx`. Inspect the accepted transformed output with `FLOAT_OP_RE` and `INTEGER_TOSA_RE`, writing:

  ```json
  {
    "float_ops": ["math.exp"],
    "integer_tosa_forms": [],
    "representation": "float" | "standard-integer-table" | "mixed" | "unknown",
    "semantic_classification": "undetermined"
  }
  ```

  At the matrix top level, write this `route_documentation` mapping and add its key as `documentation_id` to every route row. It records the authoritative basis for the route's name and classification without presenting the URL as an equivalence proof:

  ```python
  ROUTE_DOCUMENTATION = {
      "circt-scf-to-calyx": {
          "kind": "upstream-tool",
          "reference": "https://circt.llvm.org/docs/Passes/",
          "claim_boundary": "observed CIRCT acceptance is compiler-capability evidence only",
      },
      "mlir-canonicalize-and-math": {
          "kind": "upstream-tool",
          "reference": "https://mlir.llvm.org/docs/Passes/",
          "claim_boundary": "pass completion does not establish PT2E equivalence",
      },
      "torch-mlir-tosa": {
          "kind": "upstream-tool",
          "reference": "https://github.com/llvm/torch-mlir",
          "claim_boundary": "Torch-to-TOSA conversion is representation evidence only",
      },
      "mlir-tosa": {
          "kind": "upstream-specification-and-tool",
          "reference": "https://mlir.llvm.org/docs/Dialects/TOSA/",
          "claim_boundary": "a TOSA table or rescale form is not automatically exact relative to PT2E",
      },
      "llm2fpga-zero-point-compatibility": {
          "kind": "repository-local-pass",
          "reference": "tools/mlir-passes/LegalizePt2eTosaZeroPoint.cpp",
          "claim_boundary": "local compatibility transformation; not an upstream standard route",
      },
  }
  ```

  Use `circt-scf-to-calyx` for direct-CIRCT rows, `mlir-canonicalize-and-math` for canonicalization and Math-conversion rows, `torch-mlir-tosa` for the Torch-to-TOSA row, `mlir-tosa` for raw validation and TOSA-to-Linalg rows, and `llm2fpga-zero-point-compatibility` only for the zero-point legalization row.

  `math.fpowi` must use the same upstream routes as the other primitives. Do not insert a multiplication expansion or call it algebraically exact.

- [ ] **Step 5: Implement the whole-RC TOSA and Direct-Linalg evidence rows**

  Add `run_full_rc_routes()` with this ordered route sequence:

  1. `canonical-pt2e-torch-to-tosa`:

     ```python
     [
         torch_mlir_opt, str(torch_mlir),
         "--torch-fuse-quantized-ops",
         "--torch-backend-to-tosa-backend-pipeline",
         "-o", str(raw_tosa),
     ]
     ```

  2. `upstream-tosa-validate-raw`:

     ```python
     [mlir_opt, str(raw_tosa), "--pass-pipeline=builtin.module(tosa-validate)", "-o", str(raw_validated)]
     ```

  3. `local-pt2e-tosa-zero-point-legalization`: run the existing checked-in pass only as a separately named local compatibility step:

     ```python
     [
         mlir_opt, str(raw_tosa), f"--load-pass-plugin={pass_plugin}",
         "--pass-pipeline=builtin.module(llm2fpga-legalize-pt2e-tosa-zero-point,canonicalize,cse,tosa-validate)",
         "-o", str(legalized_tosa),
     ]
     ```

  4. `upstream-tosa-to-linalg-and-arith`:

     ```python
     [
         mlir_opt, str(legalized_tosa), "--tosa-to-linalg-pipeline", "--tosa-to-tensor",
         "--tosa-to-arith=include-apply-rescale", "--canonicalize", "--cse",
         "-o", str(tosa_linalg),
     ]
     ```

  5. If step 4 is accepted, invoke the existing `linalg_to_scf_no_handshake.sh`, then `scf_to_flat_scf_no_handshake.sh` with `FLAT_SCF_BLOCKER_REPORT` set, then direct CIRCT on the resulting `flat.scf.mlir`. Record every skipped step with `status: "skipped"` and the immediately preceding rejected route ID.

  6. `direct-linalg-flat-scf-to-circt`: invoke direct CIRCT on the frozen `flat.scf.mlir` without inserting any scout pass. Its failure result is part of the matrix even when the TOSA route fails earlier.

  For every valid IR output, store the operation/type census, whether it still contains float operations, whether it contains `tosa.table`, `tosa.rescale`, or `tosa.apply_rescale`, and whether direct CIRCT accepted it. Every initial full-RC row has `semantic_classification: "undetermined"` and:

  ```json
  "oracle_comparison": {
    "status": "not-run",
    "reason": "no executable transformed candidate at the PT2E raw-code boundary"
  }
  ```

  Use `subprocess.run` with argument lists. Do not invoke a shell, suppress diagnostics, or use a resource-scout transform.

- [ ] **Step 6: Link composite provenance rows to the whole-RC route rather than pretending fragments execute**

  Read `slices.json` and add one matrix row for every composite fragment. Each row must contain:

  ```json
  {
    "input_kind": "non-executable-provenance-fragment",
    "transform_status": "not-run",
    "reason": "fragment preserves source provenance and external values but is not an independently executable semantic replacement",
    "whole_rc_routes": ["canonical-pt2e-torch-to-tosa", "direct-linalg-flat-scf-to-circt"]
  }
  ```

  This preserves the link from Softmax, tanh-GELU, and LayerNorm evidence to the actual whole RC without manufacturing a smaller executable model.

- [ ] **Step 7: Add the command-line interface and write the matrix**

  `main()` must require these arguments:

  ```text
  --torch-mlir PATH
  --flat-scf PATH
  --slices PATH
  --reference PATH
  --torch-mlir-opt PATH
  --mlir-opt PATH
  --circt-opt PATH
  --pass-plugin PATH
  --linalg-to-scf-script PATH
  --scf-to-flat-scf-script PATH
  --flat-scf-blocker-report PATH
  --primitive name=PATH
  --out-dir PATH
  ```

  Accept `--primitive` multiple times. Parse each value with `name, separator, value = item.partition("=")`; reject missing names, missing paths, or duplicate names. Require exactly `exp`, `tanh`, `fpowi-cube`, and `sqrt` keys.

  Write `matrix.json` and `oracle-comparison.json` under `--out-dir`. The top-level matrix includes actual SHA-256 values for Torch-MLIR, flat-SCF, `slices.json`, and `reference.json`; tool paths and `--version` output; primitive rows; full-RC rows; and composite rows.

- [ ] **Step 8: Verify the matrix tests are GREEN**

  Run:

  ```sh
  python3 -m unittest tests.test_quantized_rc_nonlinear_matrix -v
  ```

  Expected: all tests pass. In particular, a zero-exit error-bearing fake command is rejected and neither an untested nor a scout route can be labelled exact.

- [ ] **Step 9: Commit Task 4 only**

  ```sh
  git add scripts/pipeline/run_quantized_rc_nonlinear_matrix.py \
    tests/test_quantized_rc_nonlinear_matrix.py
  git commit -m "feat: record nonlinear lowering evidence matrix"
  ```

### Task 5: Render the bounded conclusion and wire the Nix evidence bundle

**Files:**

- Create: `scripts/pipeline/render_quantized_rc_nonlinear_frontier.py`
- Create: `tests/test_quantized_rc_nonlinear_frontier_result.py`
- Modify: `flake.nix`
- Create: `tests/test_quantized_rc_nonlinear_frontier_nix.py`

**Interfaces:**

- Consumes: `matrix.json`, `slices.json`, and frozen `reference.json`.
- Produces: `result.json` and `result.md`, always with a bounded status rather than a fictitious successful hardware result.
- Nix package: `tinystories-w8a8-rc-nonlinear-lowering-frontier`.

- [ ] **Step 1: Write failing renderer tests**

  Create `tests/test_quantized_rc_nonlinear_frontier_result.py` with a minimal matrix fixture that has direct `math.sqrt` accepted and `math.exp`, `math.tanh`, and `math.fpowi` rejected. Test these exact outcomes:

  ```python
  self.assertEqual(payload["status"], "blocked-standard-route-frontier")
  self.assertEqual(payload["recommendation"]["kind"], "upstream-compiler-or-hardware-work")
  self.assertIn("math.exp", payload["first_remaining_frontier"]["operation"])
  self.assertIn("not numerical equivalence evidence", markdown)
  ```

  Add a second fixture with `route_id: "scout-tanh"`, `semantic_classification: "exact"`, and a passing comparison. Assert that rendering raises `ValueError` containing `approximate or scout`.

- [ ] **Step 2: Run the renderer tests and verify RED**

  Run:

  ```sh
  python3 -m unittest tests.test_quantized_rc_nonlinear_frontier_result -v
  ```

  Expected: import/execution failure because the renderer does not exist.

- [ ] **Step 3: Implement deterministic result rendering**

  Create `scripts/pipeline/render_quantized_rc_nonlinear_frontier.py` and export these exact functions: `load_object(path: Path) -> dict[str, object]`, `validate_routes(routes: list[dict[str, object]]) -> None`, `first_remaining_frontier(matrix: dict[str, object]) -> dict[str, object]`, `recommendation(matrix: dict[str, object]) -> dict[str, str]`, and `render_markdown(payload: dict[str, object]) -> str`. The result schema and selection rules below define their complete public behaviour.

  `validate_routes` must use the same exactness rule as Task 4: reject route IDs containing `scout` or `approx` when classified exact, and reject an exact classification unless `oracle_comparison.status == "pass"`.

  Generate the following result structure:

  ```json
  {
    "schema_version": 1,
    "status": "standard-route-advance" | "blocked-standard-route-frontier",
    "model_key": "tinystories-w8a8-rc-study-mask9-vocab6-width2",
    "oracle": {"case_ids": ["ascending", "descending", "zeros", "alternating"], "comparison": {}},
    "families": [],
    "first_remaining_frontier": {},
    "recommendation": {"kind": "standard-route-integration" | "upstream-compiler-or-hardware-work" | "separate-approximation-study", "reason": ""},
    "limits": ["No SV, DDR3, host, board, or FPGA-utilization claim is made by this result."]
  }
  ```

  Use `blocked-standard-route-frontier` unless every required nonlinear family has a valid route with CIRCT acceptance and a passing raw-code/token comparison. If no named route meets those gates, select `upstream-compiler-or-hardware-work`; do not choose an approximation study merely because TOSA has a table operation in its specification.

  The Markdown must include:

  1. fixed unit and frozen oracle;
  2. source hashes and pinned tool paths;
  3. one table with family, source operation/signature, route results, representation, CIRCT status, oracle-comparison status, and route-documentation identifier;
  4. the first remaining operation/route boundary;
  5. recommendation and explicit non-claims;
  6. a sentence that provenance fragments are not numerical equivalence evidence.

- [ ] **Step 4: Add the Nix source-slice bundle**

  In `flake.nix`, after `rcWorkingSystem` is defined, add a `quantizedRcNonlinearSlices` derivation with this body (use the existing `pipelineStagePackagesNoHandshake` bindings):

  ```nix
        quantizedRcNonlinearSlices = pkgs.runCommand
          "tinystories-w8a8-rc-nonlinear-slices" {
            nativeBuildInputs = [ python ];
          } ''
            set -euo pipefail
            ${python}/bin/python3 ${./scripts/pipeline/extract_quantized_rc_nonlinear_slices.py} \
              --torch-mlir ${pipelineStagePackagesNoHandshake."tinystories-w8a8-rc-study-mask9-vocab6-width2-torch"} \
              --flat-scf ${pipelineStagePackagesNoHandshake."tinystories-w8a8-rc-study-mask9-vocab6-width2-flat-scf"}/flat.scf.mlir \
              --model-key tinystories-w8a8-rc-study-mask9-vocab6-width2 \
              --out-dir "$out"
          '';
  ```

  The derivation must retain only `$out` artifacts. It may use Nix-builder temporary paths while executing but must not rely on a persistent `/tmp` result.

- [ ] **Step 5: Add the whole-RC frontier evidence package**

  Add this derivation immediately after `quantizedRcNonlinearSlices`:

  ```nix
        quantizedRcNonlinearFrontier = pkgs.runCommand
          "tinystories-w8a8-rc-nonlinear-lowering-frontier" {
            nativeBuildInputs = [ python torchMlir mlirForTorchMlir circt pkgs.bash ];
          } ''
            set -euo pipefail
            mkdir -p "$out"
            ${python}/bin/python3 ${./scripts/pipeline/run_quantized_rc_nonlinear_matrix.py} \
              --torch-mlir ${pipelineStagePackagesNoHandshake."tinystories-w8a8-rc-study-mask9-vocab6-width2-torch"} \
              --flat-scf ${pipelineStagePackagesNoHandshake."tinystories-w8a8-rc-study-mask9-vocab6-width2-flat-scf"}/flat.scf.mlir \
              --slices ${quantizedRcNonlinearSlices}/slices.json \
              --reference ${rcWorkingSystem.referenceImage}/reference.json \
              --torch-mlir-opt ${torchMlir}/bin/torch-mlir-opt \
              --mlir-opt ${mlirForTorchMlir}/bin/mlir-opt \
              --circt-opt ${circt}/bin/circt-opt \
              --pass-plugin ${llm2fpgaTorchMlirPasses}/lib/LLM2FPGAMLIRPasses.so \
              --linalg-to-scf-script ${noHandshakeLinalgToScf} \
              --scf-to-flat-scf-script ${noHandshakeScfToFlatScf} \
              --flat-scf-blocker-report ${flatScfBlockerReport} \
              --primitive exp=${./reproducers/calyx-math-exp/input.mlir} \
              --primitive tanh=${./reproducers/calyx-math-tanh/input.mlir} \
              --primitive fpowi-cube=${./reproducers/calyx-math-fpowi-cube/input.mlir} \
              --primitive sqrt=${./reproducers/calyx-math-sqrt/input.mlir} \
              --out-dir "$out/matrix"
            ${python}/bin/python3 ${./scripts/pipeline/render_quantized_rc_nonlinear_frontier.py} \
              --matrix "$out/matrix/matrix.json" \
              --slices ${quantizedRcNonlinearSlices}/slices.json \
              --reference ${rcWorkingSystem.referenceImage}/reference.json \
              --out-json "$out/result.json" \
              --out-markdown "$out/result.md"
            test -f "$out/matrix/matrix.json"
            test -f "$out/matrix/oracle-comparison.json"
            test -f "$out/result.json"
            test -f "$out/result.md"
          '';
  ```

  Expose both names in `packages`:

  ```nix
          "tinystories-w8a8-rc-nonlinear-slices" = quantizedRcNonlinearSlices;
          "tinystories-w8a8-rc-nonlinear-lowering-frontier" = quantizedRcNonlinearFrontier;
  ```

  Do not add the full frontier package to `checks`; it intentionally runs the full frozen RC evidence experiment and should remain an explicit package build.

- [ ] **Step 6: Add the Nix wiring contract test**

  Create `tests/test_quantized_rc_nonlinear_frontier_nix.py` with these assertions:

  ```python
  import unittest
  from pathlib import Path


  ROOT = Path(__file__).resolve().parents[1]


  class QuantizedRcNonlinearFrontierNixTest(unittest.TestCase):
      def test_frontier_package_uses_frozen_rc_and_named_routes(self) -> None:
          flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
          self.assertIn("quantizedRcNonlinearSlices", flake)
          self.assertIn("quantizedRcNonlinearFrontier", flake)
          self.assertIn('"tinystories-w8a8-rc-nonlinear-lowering-frontier"', flake)
          self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", flake)
          self.assertIn("extract_quantized_rc_nonlinear_slices.py", flake)
          self.assertIn("run_quantized_rc_nonlinear_matrix.py", flake)
          self.assertIn("render_quantized_rc_nonlinear_frontier.py", flake)
          self.assertIn("--torch-backend-to-tosa-backend-pipeline", (ROOT / "scripts/pipeline/run_quantized_rc_nonlinear_matrix.py").read_text(encoding="utf-8"))
          self.assertIn("--tosa-to-linalg-pipeline", (ROOT / "scripts/pipeline/run_quantized_rc_nonlinear_matrix.py").read_text(encoding="utf-8"))
          self.assertNotIn("lower-scout-math-for-calyx", (ROOT / "scripts/pipeline/run_quantized_rc_nonlinear_matrix.py").read_text(encoding="utf-8"))


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 7: Verify renderer and Nix-wiring tests are GREEN**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_quantized_rc_nonlinear_frontier_result \
    tests.test_quantized_rc_nonlinear_frontier_nix \
    -v
  nix eval .#tinystories-w8a8-rc-nonlinear-lowering-frontier.name
  ```

  Expected: Python tests pass and Nix evaluates the package name without building it.

- [ ] **Step 8: Commit Task 5 only**

  ```sh
  git add scripts/pipeline/render_quantized_rc_nonlinear_frontier.py \
    tests/test_quantized_rc_nonlinear_frontier_result.py \
    tests/test_quantized_rc_nonlinear_frontier_nix.py \
    flake.nix
  git commit -m "feat: package nonlinear lowering frontier evidence"
  ```

### Task 6: Run the bounded experiment, publish its actual result, and verify the repository boundary

**Files:**

- Create: `docs/results/2026-07-16-quantized-rc-nonlinear-lowering-frontier.md`
- Modify: `docs/results/2026-07-16-quantized-rc-working-system.md`
- Modify: `tests/test_quantized_rc_nonlinear_frontier_result.py`

**Interfaces:**

- Consumes: the Nix output of `tinystories-w8a8-rc-nonlinear-lowering-frontier`.
- Produces: a Git-tracked result document copied verbatim from the renderer and a corrected working-system link.
- Invariant: the document reports actual execution evidence. It never substitutes expected results, guessed resource usage, or a claim of equivalence.

- [ ] **Step 1: Run focused tests before the full evidence derivation**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_scf_to_calyx_no_handshake \
    tests.test_calyx_float_nix_package \
    tests.test_quantized_rc_nonlinear_slices \
    tests.test_fpga_transformer_nonlinear_practice_survey \
    tests.test_quantized_rc_nonlinear_matrix \
    tests.test_quantized_rc_nonlinear_frontier_result \
    tests.test_quantized_rc_nonlinear_frontier_nix \
    -v
  git diff --check
  ```

  Expected: all focused tests pass and `git diff --check` produces no output.

- [ ] **Step 2: Build the primitive and full evidence packages**

  Run:

  ```sh
  nix build .#calyx-math-exp-upstream-reproducer -L --no-link --print-out-paths
  nix build .#tinystories-w8a8-rc-nonlinear-slices -L --no-link --print-out-paths
  nix build .#tinystories-w8a8-rc-nonlinear-lowering-frontier -L --no-link --print-out-paths
  ```

  Expected: every command returns a Nix output path. The frontier package may report `blocked-standard-route-frontier` in `result.json`; that is a successful evidence build, not a hardware success claim.

- [ ] **Step 3: Inspect and retain the actual evidence**

  Set `FRONTIER_OUT` to the output path printed by the final command and inspect only durable Nix output files:

  ```sh
  sed -n '1,260p' "$FRONTIER_OUT/result.json"
  sed -n '1,320p' "$FRONTIER_OUT/result.md"
  sed -n '1,260p' "$FRONTIER_OUT/matrix/matrix.json"
  ```

  Confirm all of these before publishing:

  - every recorded tool path and source SHA-256 is present;
  - `math.exp`, `math.tanh`, and constant-3 `math.fpowi` appear as actual primitive observations;
  - Softmax, tanh-GELU, and LayerNorm provenance fragments name source ranges and retained external values;
  - a diagnostic-bearing zero exit is marked rejected;
  - no route is labelled exact unless `oracle_comparison.status` is `pass`;
  - no SV, DDR3, host, board, or resource-utilization result appears in the renderer output.

- [ ] **Step 4: Publish the generated result verbatim**

  Read `$FRONTIER_OUT/result.md` and create `docs/results/2026-07-16-quantized-rc-nonlinear-lowering-frontier.md` with exactly that generated Markdown, using `apply_patch`. Do not edit its conclusions by hand.

  In `docs/results/2026-07-16-quantized-rc-working-system.md`, replace the phrase `5 'math.sqrt'` with this exact sentence:

  ```markdown
  5 source `math.rsqrt` operations, which the existing local pre-Calyx helper
  rewrites into a `math.sqrt`-based control path; this is not an end-to-end
  equivalence result.
  ```

  Add this exact link under the immediate-lowerer frontier section:

  ```markdown
  The named-route investigation and its frozen-source provenance are recorded in
  [the nonlinear lowering frontier result](2026-07-16-quantized-rc-nonlinear-lowering-frontier.md).
  ```

- [ ] **Step 5: Add a result-document regression assertion**

  Extend `tests/test_quantized_rc_nonlinear_frontier_result.py` with:

  ```python
  def test_published_result_keeps_the_bounded_claim(self) -> None:
      result = ROOT / "docs" / "results" / "2026-07-16-quantized-rc-nonlinear-lowering-frontier.md"
      text = result.read_text(encoding="utf-8")
      self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", text)
      self.assertIn("not numerical equivalence evidence", text)
      self.assertIn("No SV, DDR3, host, board, or FPGA-utilization claim", text)
      self.assertNotIn("resource-scout approximation", text.lower())
  ```

- [ ] **Step 6: Run final verification**

  Run:

  ```sh
  python3 -m unittest \
    tests.test_scf_to_calyx_no_handshake \
    tests.test_calyx_float_nix_package \
    tests.test_quantized_rc_nonlinear_slices \
    tests.test_fpga_transformer_nonlinear_practice_survey \
    tests.test_quantized_rc_nonlinear_matrix \
    tests.test_quantized_rc_nonlinear_frontier_result \
    tests.test_quantized_rc_nonlinear_frontier_nix \
    -v
  nix build .#tinystories-w8a8-rc-nonlinear-lowering-frontier -L --no-link
  git diff --check
  git status --short
  ```

  Expected: tests pass; the Nix build produces the evidence bundle; whitespace check is clean; only this task’s files are staged or unstaged for the final commit.

- [ ] **Step 7: Commit Task 6 only**

  ```sh
  git add docs/results/2026-07-16-quantized-rc-nonlinear-lowering-frontier.md \
    docs/results/2026-07-16-quantized-rc-working-system.md \
    tests/test_quantized_rc_nonlinear_frontier_result.py
  git commit -m "docs: record quantized RC nonlinear frontier"
  ```

## Final handoff criteria

The work is ready to hand off only when all of the following are true:

1. The error-bearing CIRCT partial output is rejected by the wrapper and covered by a behavioral regression test.
2. Primitive MRCs match actual RC scalar signatures: f32 exp, f32 tanh, f32/i64-3 fpowi, and f32 sqrt control.
3. Composite provenance fragments are generated from the frozen RC Torch-MLIR, contain source SHA-256/ranges/external values, and explicitly deny executable-equivalence status.
4. The Nix package records raw TOSA validation, separately labelled local zero-point legalization, upstream TOSA lowering, upstream Math transformations, and direct CIRCT outcomes.
5. The evidence matrix rejects a zero-exit error diagnostic and rejects an exact claim without all six codes plus token ID matching on every frozen corpus case.
6. The Git-tracked result document is copied from the actual deterministic renderer output and states the first remaining frontier or a truly validated standard-route advance.
7. The source-grounded survey clearly distinguishes published LUT, polynomial, iterative, and model-reformulation practice from a semantic-equivalence proof or approved RC route.
8. No new SV, DDR3, host, board, FPGA-utilization, or approximation claim is introduced.
