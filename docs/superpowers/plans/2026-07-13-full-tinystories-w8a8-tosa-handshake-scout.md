# Full TinyStories W8A8 TOSA–Handshake Scout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect full TinyStories PT2E W8A8 through validated TOSA to the existing Handshake/HW/SV backend and record the genuine Yosys or compiler frontier.

**Architecture:** Add a public alias over the existing `tinystories-w8a8` TOSA pipeline and reuse the established Linalg-to-CF-to-Handshake-to-HW-to-SV stages. Run the target under monitoring and preserve machine-readable evidence without treating QDQ-heavy output as integer-only hardware.

**Tech Stack:** Nix flakes, Python `unittest`, Torch-MLIR/TOSA, MLIR, CIRCT Handshake/HW/SV, Yosys, Markdown, JSON.

## Global Constraints

- The route must contain TOSA and Handshake and must not contain Calyx.
- Reuse existing model and pipeline constructors; do not duplicate lowering logic.
- Generated SV must be genuine output, never a placeholder.
- Record the first genuine failure when SV or Yosys is not reached.
- Report residual floating-point operations and external FP primitives.
- Equivalence, quality validation, board validation, representative calibration, and SmoothQuant are out of scope.

---

### Task 1: Register the full-model TOSA–Handshake alias

**Files:**
- Modify: `tests/test_full_tinystories_w8a8_scout.py`
- Modify: `flake.nix`

**Interfaces:**
- Consumes: `pipelineStagePackagesTosa`, `handshakeSvStages`, model key `tinystories-w8a8`.
- Produces: `tinystories-w8a8-via-tosa-<stage>`, including `tinystories-w8a8-via-tosa-yosys-stat`.

- [ ] **Step 1: Write the failing alias regression**

Add this test, using the file's existing `ROOT` and `re` imports:

```python
def test_full_model_w8a8_has_tosa_handshake_sv_alias(self):
    flake = (ROOT / "flake.nix").read_text()
    match = re.search(
        r'\{\s*alias = "tinystories-w8a8-via-tosa";(?P<body>.*?)\n\s*\}',
        flake,
        re.DOTALL,
    )
    self.assertIsNotNone(match)
    body = match.group("body")
    self.assertIn('model = "tinystories-w8a8";', body)
    self.assertIn('frontend = "tosa";', body)
    self.assertIn('backend = "handshake-sv";', body)
    self.assertIn("packages = pipelineStagePackagesTosa;", body)
    self.assertIn("stages = handshakeSvStages;", body)
    self.assertNotIn("calyx", body.lower())
```

- [ ] **Step 2: Run the test and verify RED**

```bash
python3 -m unittest discover -s tests -p 'test_full_tinystories_w8a8_scout.py' -v
```

Expected: `FAIL` because the alias does not exist.

- [ ] **Step 3: Add the minimal alias to `pipelineAliasSpecs`**

```nix
{
  alias = "tinystories-w8a8-via-tosa";
  model = "tinystories-w8a8";
  frontend = "tosa";
  backend = "handshake-sv";
  packages = pipelineStagePackagesTosa;
  stages = handshakeSvStages;
}
```

- [ ] **Step 4: Verify and commit**

```bash
python3 -m unittest discover -s tests -p 'test_full_tinystories_w8a8_scout.py' -v
nix flake check --no-build
git add flake.nix tests/test_full_tinystories_w8a8_scout.py
git commit -m "feat: expose W8A8 TOSA handshake pipeline"
```

Expected: tests pass, flake evaluation passes, and the alias commit succeeds.

### Task 2: Run and record the complete monitored scout

**Files:**
- Create: `artifacts/full-tinystories-pt2e-w8a8-tosa-handshake-scout/result.json`
- Create: `docs/results/2026-07-13-full-tinystories-pt2e-w8a8-tosa-handshake-scout.md`

**Interfaces:**
- Consumes: `tinystories-w8a8-via-tosa-yosys-stat` and `scripts/pipeline/monitor_build.sh`.
- Produces: machine-readable and human-readable terminal evidence.

- [ ] **Step 1: Run the monitored target**

```bash
scripts/pipeline/monitor_build.sh \
  /tmp/full-tinystories-w8a8-tosa-handshake-scout 5 -- \
  nix build .#tinystories-w8a8-via-tosa-yosys-stat \
  --no-link --print-out-paths -L
```

Expected: terminate with either a real Yosys artifact or the first compiler failure.

- [ ] **Step 2: Inspect the terminal frontier**

```bash
sed -n '1,200p' /tmp/full-tinystories-w8a8-tosa-handshake-scout/summary.txt
rg -n "error:|failed|Unhandled|unsupported|killed|out of memory" \
  /tmp/full-tinystories-w8a8-tosa-handshake-scout
```

Expected: identify exit status, wall time, sampled peak RSS, and the first failing stage, or confirm Yosys completion.

- [ ] **Step 3: Measure only artifacts actually reached**

Run `wc -l -c` on textual MLIR/SV artifacts, `du -sb` on directory artifacts, inspect `sources.f`, and parse actual Yosys stat JSON if present. Use `rg` over reached IR/SV to count residual float operations and referenced FP primitives. Do not encode absent stages as zero-sized artifacts.

- [ ] **Step 4: Create `result.json` using this schema**

```json
{
  "schema_version": 1,
  "date": "2026-07-13",
  "target": "tinystories-w8a8-via-tosa-yosys-stat",
  "route": ["torch", "tosa", "linalg", "cf", "handshake", "hw0", "hw", "hw-clean", "sv-mlir", "sv", "yosys-stat"],
  "uses_calyx": false,
  "status": "observed-status",
  "last_successful_stage": "observed-stage",
  "first_failure": null,
  "monitor": {"exit_code": 0, "wall_seconds": 0, "sample_period_seconds": 5, "peak_sampled_vmrss_kib": 0},
  "artifacts": {},
  "float_frontier": {},
  "sv_generated": false,
  "yosys_statistics_generated": false,
  "yosys_statistics": null
}
```

Replace every observational value. On failure, use `status: "failed"` and an object with `stage` and `message` for `first_failure`.

- [ ] **Step 5: Write and validate the report**

The report must include outcome, exact command, route, terminal frontier, timing/memory, artifact sizes, float/FP primitive evidence, SV/Yosys status, and interpretation. Explicitly state that SV does not establish integer-only hardware.

```bash
python3 -m json.tool artifacts/full-tinystories-pt2e-w8a8-tosa-handshake-scout/result.json >/dev/null
git diff --check
git add artifacts/full-tinystories-pt2e-w8a8-tosa-handshake-scout/result.json \
  docs/results/2026-07-13-full-tinystories-pt2e-w8a8-tosa-handshake-scout.md
git commit -m "docs: record W8A8 TOSA handshake scout"
```

Expected: valid JSON, clean diff, and committed evidence.

### Task 3: Update the baseline and verify the repository

**Files:**
- Modify: `docs/current-baseline.md`
- Modify: `tests/test_full_tinystories_w8a8_scout.py`

**Interfaces:**
- Consumes: Task 2's observed result.
- Produces: a discoverable current frontier and verified repository state.

- [ ] **Step 1: Write the failing baseline test**

```python
def test_current_baseline_records_w8a8_tosa_handshake_scout(self):
    baseline = (ROOT / "docs/current-baseline.md").read_text()
    self.assertIn("tinystories-w8a8-via-tosa-yosys-stat", baseline)
    self.assertIn("TOSA -> Linalg -> CF -> Handshake -> HW -> SV", baseline)
    self.assertIn("Calyx: not used", baseline)
```

- [ ] **Step 2: Run the named test and verify RED**

Expected: `FAIL` because the baseline lacks the new result.

- [ ] **Step 3: Add the concise baseline section**

Add a dated section near the top of `docs/current-baseline.md` containing the target, route, `Calyx: not used`, last successful stage, first failure or Yosys summary, and a link to Task 2's report.

- [ ] **Step 4: Run final verification**

```bash
python3 -m unittest discover -s tests -v
nix build .#llm2fpgaMlirPasses .#llm2fpgaTorchMlirPasses --no-link -L
nix flake check --no-build
python3 -m json.tool artifacts/full-tinystories-pt2e-w8a8-tosa-handshake-scout/result.json >/dev/null
git diff --check
```

Expected: tests pass, both plugin builds succeed, flake outputs evaluate, JSON is valid, and the diff is clean.

- [ ] **Step 5: Commit the baseline**

```bash
git add docs/current-baseline.md tests/test_full_tinystories_w8a8_scout.py
git commit -m "docs: update W8A8 handshake frontier"
```
