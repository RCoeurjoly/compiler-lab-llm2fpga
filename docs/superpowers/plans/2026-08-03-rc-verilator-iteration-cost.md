# RC Verilator Iteration-Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V=6 RC's cached Verilator simulation loop quieter, reusable across the frozen corpus, semantically safe to normalize, and independently measurable by front-end/build/runtime stage.

**Architecture:** Keep the raw Calyx SV and all W8A8 artifacts immutable.  The Python runner emits a runtime-configurable fixture and a conservative continuous-expression normalization.  It invokes Verilator code generation and generated-C++ compilation as separate stages, while a Nix diagnostic records a small one-factor configuration matrix.

**Tech Stack:** Python 3 standard library, SystemVerilog, Verilator 5.022+, GNU make, Nix, `unittest`.

## Global Constraints

- Preserve the exact four frozen contexts, six raw signed-int8 codes, and lowest-index argmax contract.
- Do not alter raw Calyx SV, PT2E export, image bytes/manifest, W8A8 arithmetic, or one-cycle fixture memory protocol.
- Treat `X`/`Z`, SystemVerilog sizing, signedness, and conditional semantics as observable; decline a normalizer rewrite unless its shape is proven.
- Keep heartbeat=1 and output-write traces available only in explicitly named diagnostics; normal builds are quiet.
- Retain `--verilator-jobs` compatibility for existing diagnostics while adding separate code-generation and C++ build job controls.
- Nix-built artifacts, not `/tmp` output, are the durable performance evidence.

---

### Task 1: Lock down fixture runtime controls

**Files:**
- Modify: `tests/test_rc_sv_equivalence_fixture.py`
- Modify: `scripts/pipeline/run_rc_sv_equivalence.py:48-219,279-390`
- Modify: `flake.nix:819-854`
- Modify: `diagnostics/rc-first-output.nix`
- Modify: `diagnostics/rc-first-output-run.nix`

**Interfaces:**
- Produces: `_fixture(..., heartbeat_cycles, case_id, stop_after_output, trace_output_writes)` whose generated SV accepts `+heartbeat_cycles`, `+timeout_cycles`, `+case_index`, `+stop_after_output`, and `+trace_output_writes`.
- Produces: `_runtime_args(args, reference) -> list[str]`, used by both normal and `--run-only` execution.

- [ ] **Step 1: Write failing fixture-rendering tests**

```python
def test_fixture_runtime_controls_allow_quiet_cached_runs(self):
    tb = self._fixture_text(heartbeat_cycles=0, case_id="ascending")
    self.assertIn('$value$plusargs("heartbeat_cycles=%d", heartbeat_cycles)', tb)
    self.assertIn("if (heartbeat_cycles > 0) begin", tb)
    self.assertNotIn("% 0", tb)
    self.assertIn("selected_case_index", tb)
    self.assertIn('RESULT ascending', tb)
    self.assertIn('RESULT descending', tb)

def test_runtime_args_select_case_without_rebuilding_fixture(self):
    args = self._args(case_id="ascending", heartbeat_cycles=0)
    self.assertIn("+case_index=0", module._runtime_args(args, self.reference))
    self.assertIn("+heartbeat_cycles=0", module._runtime_args(args, self.reference))
```

- [ ] **Step 2: Run the focused test module and verify the new tests fail**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture -v`

Expected: FAIL because the fixture bakes case filtering and does not expose `_runtime_args` or plusargs.

- [ ] **Step 3: Implement runtime controls without changing memory behavior**

```python
def _runtime_args(args: argparse.Namespace, reference: dict) -> list[str]:
    result = [
        f"+heartbeat_cycles={args.heartbeat_cycles}",
        f"+timeout_cycles={args.timeout_cycles}",
        f"+stop_after_output={int(args.stop_after_output)}",
        f"+trace_output_writes={int(args.trace_output_writes)}",
    ]
    if args.case_id is not None:
        result.append(f"+case_index={_case_index(reference, args.case_id)}")
    return result
```

Emit all reference cases in `_fixture`; wrap each static case block in the
testbench's `selected_case_index` condition.  Place `$value$plusargs` calls in
the same `initial` block as the case loop.  Guard heartbeat modulo evaluation
with an outer `if (heartbeat_cycles > 0)` and guard `OUTWRITE` with the trace
flag.  Pass the plusargs to the Verilator binary in both normal and run-only
paths.  Reject negative heartbeat/timeout values before fixture generation.

- [ ] **Step 4: Make the normal Nix build quiet and preserve diagnostics**

Set `flake.nix`'s exact cached build to `--heartbeat-cycles 0`.  Continue
passing the explicit diagnostic heartbeat interval in `rc-first-output.nix`
and add `--trace-output-writes` where `OUTWRITE` evidence is consumed.

- [ ] **Step 5: Run focused tests and a fixture-only rendering check**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture -v`

Run: `python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py`

Expected: PASS; generated quiet TB has no modulo-zero literal and the trace
diagnostic still has `OUTWRITE` enabled.

- [ ] **Step 6: Commit**

```bash
git add tests/test_rc_sv_equivalence_fixture.py scripts/pipeline/run_rc_sv_equivalence.py flake.nix diagnostics/rc-first-output.nix diagnostics/rc-first-output-run.nix
git commit -m "feat: reuse quiet RC Verilator fixture"
```

### Task 2: Replace procedural FSM normalization with continuous pages

**Files:**
- Modify: `tests/test_rc_sv_equivalence_fixture.py`
- Modify: `scripts/pipeline/run_rc_sv_equivalence.py:221-276`
- Create: `diagnostics/rc-sv-normalizer-semantics.nix`

**Interfaces:**
- Produces: `_normalize_large_or_assignments(source: str) -> str` with
  `NORMALIZER_PAGE_TERMS` as its bounded-page constant.
- Produces: a JSON/console normalizer report with transformed assignment/page
  counts for use in the Nix measurement artifact.

- [ ] **Step 1: Write failing structural tests for genuinely large sources**

```python
def test_large_scalar_or_is_rewritten_as_continuous_bounded_pages(self):
    terms = [f"term_{i}" for i in range(4_000)]
    source = "logic en; assign en = " + " | ".join(terms) + ";"
    normalized = module._normalize_large_or_assignments(source)
    self.assertNotIn("always_comb", normalized)
    self.assertNotIn(" if (", normalized)
    self.assertEqual(re.findall(r"term_\\d+", normalized), terms)
    self.assertLessEqual(max(self._or_page_sizes(normalized)), module.NORMALIZER_PAGE_TERMS)

def test_large_proven_ternary_uses_ordered_continuous_pages(self):
    source = self._flat_ternary("state", width=13, arms=2_000)
    normalized = module._normalize_large_or_assignments(source)
    self.assertNotIn("always_comb", normalized)
    self.assertIn("wire [12:0] __llm2fpga_sim_", normalized)
    self.assertIn("cond_0 ? 13'd0", normalized)
    self.assertIn("cond_1999 ? 13'd1999", normalized)

def test_unproven_wide_or_or_ternary_is_unchanged(self):
    self.assertEqual(module._normalize_large_or_assignments(self._large_wide_or()), self._large_wide_or())
    self.assertEqual(module._normalize_large_or_assignments(self._mixed_width_ternary()), self._mixed_width_ternary())
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture -v`

Expected: FAIL because the existing normalizer emits `always_comb`/`if` and
does not page continuous expressions.

- [ ] **Step 3: Implement conservative OR and ternary page rendering**

Use only `wire` plus `assign` for generated pages.  For scalar OR, group
flat ` | ` terms recursively into pages of at most
`NORMALIZER_PAGE_TERMS`, retaining every original term verbatim.  For ternary,
parse the false-tail chain and transform only when all arms/default are
unsigned explicitly sized literals matching an unsigned numeric packed
destination declaration.  Build false-tail pages from the last chunk towards
the first:

```python
def _priority_chain(pairs: list[tuple[str, str]], fallback: str) -> str:
    result = fallback
    for condition, true_value in reversed(pairs):
        result = f"{condition} ? {true_value} : {result}"
    return result
```

Use a hash-derived temporary identifier and decline a rewrite if the identifier
already exists.  Do not replace unknown/mixed width/signed/nested constructs.

- [ ] **Step 4: Add a four-state simulator self-test**

The Nix derivation writes an original and normalized tiny SV module, drives
every `0`, `1`, `x`, and `z` condition combination including a page boundary,
and fails on `!==`.  It must verify both OR and the proven-width ternary
normalization.  It is a normalizer test, not evidence for the full RC.

- [ ] **Step 5: Run focused tests and the semantic Nix derivation**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture -v`

Run: `nix build .#tinystories-w8a8-rc-sv-normalizer-semantics -L`

Expected: PASS; the generated semantic result records every four-state case as
equal.

- [ ] **Step 6: Commit**

```bash
git add tests/test_rc_sv_equivalence_fixture.py scripts/pipeline/run_rc_sv_equivalence.py diagnostics/rc-sv-normalizer-semantics.nix flake.nix
git commit -m "fix: preserve four-state semantics in RC FSM normalization"
```

### Task 3: Split Verilator code generation from native compilation

**Files:**
- Modify: `tests/test_rc_sv_equivalence_fixture.py`
- Modify: `scripts/pipeline/run_rc_sv_equivalence.py:279-390`
- Modify: `flake.nix:819-854`

**Interfaces:**
- Produces: `--verilate-jobs`, `--build-jobs`, and compatibility
  `--verilator-jobs` resolution.
- Produces: compile JSON with `verilator_codegen_seconds`,
  `cpp_build_seconds`, generated-C++ count/bytes, binary bytes, and resolved
  configuration.

- [ ] **Step 1: Write failing command/measurement tests**

```python
def test_verilator_compile_is_two_semantic_stages(self):
    commands = self._captured_compile_commands(verilate_jobs=3, build_jobs=7)
    self.assertIn("--cc", commands[0])
    self.assertIn("--exe", commands[0])
    self.assertIn("--main", commands[0])
    self.assertEqual(commands[1][:5], ["make", "-C", self.obj_dir, "-f", "Vtb.mk"])
    self.assertIn("-j", commands[1])
    self.assertIn("7", commands[1])
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture -v`

Expected: FAIL because the runner invokes one `--binary` command.

- [ ] **Step 3: Implement separate commands and artifact metrics**

Construct Verilator with `--cc --exe --main --timing --Wno-fatal -O3`, the
existing split and thread options, and resolved `--verilate-jobs`.  Invoke
`make -C <obj_dir> -f Vtb.mk -j <build_jobs> Vtb` next.  Measure each command
with `time.perf_counter()`, summarize generated C++ after stage one, and
summarize the binary after stage two.  Preserve the Icarus path unchanged.

- [ ] **Step 4: Update exact build to state all non-diagnostic settings**

Pass explicit quiet heartbeat, `--verilate-jobs`, `--build-jobs`, split values,
and thread count in the canonical build, so comparisons do not depend on runner
defaults.

- [ ] **Step 5: Run focused tests and compile syntax checks**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture -v`

Run: `python3 -m py_compile scripts/pipeline/run_rc_sv_equivalence.py`

Expected: PASS; compilation JSON exposes distinct codegen/build fields.

- [ ] **Step 6: Commit**

```bash
git add tests/test_rc_sv_equivalence_fixture.py scripts/pipeline/run_rc_sv_equivalence.py flake.nix
git commit -m "feat: measure RC Verilator codegen and C++ build separately"
```

### Task 4: Add a controlled Nix configuration matrix and validate promotion

**Files:**
- Create: `diagnostics/rc-verilator-config-matrix.nix`
- Modify: `flake.nix`
- Create: `docs/results/2026-08-03-rc-verilator-iteration-cost.md`

**Interfaces:**
- Produces: a Nix package `tinystories-w8a8-rc-verilator-config-matrix` with
  `summary.json`, per-config compile JSON, and bounded-run results.
- Consumes: a list of named configurations with `verilateJobs`, `buildJobs`,
  `outputSplit`, `outputSplitCfuncs`, and `threads`.

- [ ] **Step 1: Write a flake-source regression test**

```python
def test_flake_exposes_rc_verilator_config_matrix(self):
    source = (ROOT / "flake.nix").read_text()
    self.assertIn('"tinystories-w8a8-rc-verilator-config-matrix"', source)
    self.assertTrue((ROOT / "diagnostics/rc-verilator-config-matrix.nix").is_file())
```

- [ ] **Step 2: Run the regression test and verify failure**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture -v`

Expected: FAIL because no matrix package exists.

- [ ] **Step 3: Implement a small one-factor default matrix**

Use fresh work directories and the same frozen SV/image/reference for every
point.  The default matrix must contain at most three compile points: the
explicit canonical baseline, one code-generation/build-job variant, and one
split variant.  It writes one JSON object per point and a summary sorted by
total compile time.  Do not run an unbounded Cartesian sweep in a default Nix
build.  Accept additional configurations only through explicit Nix parameters.

- [ ] **Step 4: Run the matrix and promote one candidate carefully**

Run: `nix build .#tinystories-w8a8-rc-verilator-config-matrix -L`

Then run the best candidate as a one-case exact smoke, followed by the existing
four-case exact gate using its cached binary.  Record wall time, stage metrics,
runtime result, raw-code equality, and token equality in the dated result
document.  If a gate cannot finish, record the timeout/frontier exactly; do not
call the configuration a pass.

- [ ] **Step 5: Run repository-level relevant checks**

Run: `python3 -m unittest tests.test_rc_sv_equivalence_fixture tests.test_rc_working_contract tests.test_rc_working_nix_wiring -v`

Expected: PASS.  Preserve existing unrelated dirty worktree changes.

- [ ] **Step 6: Commit**

```bash
git add diagnostics/rc-verilator-config-matrix.nix flake.nix docs/results/2026-08-03-rc-verilator-iteration-cost.md tests/test_rc_sv_equivalence_fixture.py
git commit -m "feat: add controlled RC Verilator configuration matrix"
```

## Self-review

- **Spec coverage:** Task 1 implements the reusable quiet runner; Task 2
  handles four-state-safe normalization; Task 3 creates independently measured
  build stages; Task 4 creates durable configuration evidence and applies the
  frozen promotion gates.
- **Placeholder scan:** The plan names concrete files, interfaces, commands,
  test assertions, options, and artifact fields.  There are no undecided
  implementation placeholders.
- **Type consistency:** `_runtime_args` consumes the parsed namespace and
  reference dictionary; the runner passes its returned strings directly to the
  Verilator binary.  Every matrix field maps to the CLI's resolved compile
  configuration.
