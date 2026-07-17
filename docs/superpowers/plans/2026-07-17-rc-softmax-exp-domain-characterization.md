# RC Softmax-Exponent Domain Characterization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Produce a Nix-packaged, exhaustive, read-only measurement of the two frozen PT2E W8A8 representative-core Softmax exponent-input domains.

**Architecture:** A Python analyzer loads the frozen exported program unchanged, discovers the two aten.softmax.int nodes and their immediate affine int8 quantize/dequantize boundaries, and uses torch.fx.Interpreter to observe f32 Softmax inputs while forwarding every original operation. It summarizes exact f32 words and an analysis-only stabilized input - amax(input) operand by deterministic base-six input shard; a reducer proves exhaustive shard coverage. Separate pilot and exhaustive Nix derivations make the evidence reproducible without retaining per-context traces.

**Tech Stack:** Python 3, PyTorch/PT2E, torch.fx.Interpreter, Nix runCommand, JSON, unittest.

## Global Constraints

- The numerical authority is exactly tinystories-w8a8-rc-study-mask9-vocab6-width2 PT2E W8A8, loaded from its frozen exported program.
- Do not re-export, re-calibrate, edit the PT2E graph, alter the model, change compiler passes, or emit SV in this work.
- Execute every intercepted Softmax through its original target; the analyzer may only observe values and calculate derived_pre_exp_operand = input - amax(input, dim=-1, keepdim=True) outside the canonical graph.
- The enumeration is lexical base-six over the half-open interval [0, 6^8) and supports auditable half-open shards [start, stop).
- Record only streaming summaries and exact observed f32 bit patterns; do not retain a trace per input context.
- Verify the frozen boundary: exactly two Softmax sites, each immediately fed by f32 dequantization of int8 codes with scale 2^-12, zero point -124, and range [-128, 127].
- Treat 256 distinct observed input and derived-pre-exp bit patterns per site as a validated upper bound; fail on a violation rather than truncating.
- The four-case corpus is a pilot only. The final conclusion requires exhaustive 6^8 = 1,679,616 context coverage or a documented, measured scalability blocker.
- Do not claim a new model, an operation-level equivalence proof, RC SV, resource utilization, DDR3 behavior, or board behavior.
- All durable products stay in the repository or Nix store; do not leave required artifacts in /tmp.

---

## File Structure

- Create: scripts/pipeline/characterize_rc_softmax_exp_domain.py — immutable-export loader, FX boundary discovery, observer, shard runner, and reducer CLI.
- Create: tests/test_rc_softmax_exp_domain.py — pure unit and small FX-graph tests for decoding, boundary validation, bit accounting, and merge coverage.
- Create: tests/test_rc_softmax_exp_domain_nix.py — static Nix wiring assertions for pilot and exhaustive derivations.
- Modify: flake.nix — expose pilot and exhaustive domain-characterization packages under stable names.
- Create: docs/results/2026-07-17-rc-softmax-exp-domain.md — evidence interpretation with immutable source hashes and measured pilot/full outputs.
- Create: tests/test_rc_softmax_exp_domain_result.py — prevents the result document from claiming a lowered implementation or equivalence.

### Task 1: Define the deterministic domain and immutable source contract

**Files:**

- Create: tests/test_rc_softmax_exp_domain.py
- Create: scripts/pipeline/characterize_rc_softmax_exp_domain.py

**Interfaces:**

- Produces context_from_index(index: int) -> list[int] using VOCAB_SIZE and CONTEXT_LENGTH from TinyStories.rc_working_contract.
- Produces sha256_file(path: Path) -> str and source_receipt(exported_program_dir: Path) -> dict[str, object].
- Later tasks consume a canonical lexical input context and a receipt containing exported-program, manifest, and analyzer SHA-256 values.

- [ ] **Step 1: Write the failing deterministic-decoding and receipt tests**

~~~python
def test_context_from_index_is_lexical_base_six() -> None:
    self.assertEqual(module.context_from_index(0), [0] * 8)
    self.assertEqual(module.context_from_index(1), [0, 0, 0, 0, 0, 0, 0, 1])
    self.assertEqual(module.context_from_index(6), [0, 0, 0, 0, 0, 0, 1, 0])
    self.assertEqual(module.context_from_index(6**8 - 1), [5] * 8)
    with self.assertRaisesRegex(ValueError, "outside"):
        module.context_from_index(6**8)

def test_source_receipt_hashes_only_frozen_inputs(tmp_path: Path) -> None:
    exported = tmp_path / "exported"
    exported.mkdir()
    (exported / "exported.pt2").write_bytes(b"frozen program")
    (exported / "manifest.json").write_text("{\"schema_version\": 1}\\n")
    receipt = module.source_receipt(exported)
    self.assertEqual(receipt["source_model_key"], RC_WORKING_SOURCE_MODEL_KEY)
    self.assertEqual(receipt["exported_program_sha256"], hashlib.sha256(b"frozen program").hexdigest())
    self.assertEqual(receipt["export_manifest_sha256"], hashlib.sha256(b"{\"schema_version\": 1}\\n").hexdigest())
    self.assertEqual(len(receipt["analyzer_sha256"]), 64)
~~~

- [ ] **Step 2: Run the test to verify it fails before implementation**

Run: python -m unittest tests/test_rc_softmax_exp_domain.py -v

Expected: FAIL because the analyzer and its public functions do not exist.

- [ ] **Step 3: Implement only the deterministic helpers and module loader**

~~~python
def context_from_index(index: int) -> list[int]:
    total = VOCAB_SIZE ** CONTEXT_LENGTH
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < total:
        raise ValueError(f"context index outside [0, {total}): {index!r}")
    result = [0] * CONTEXT_LENGTH
    for position in range(CONTEXT_LENGTH - 1, -1, -1):
        result[position] = index % VOCAB_SIZE
        index //= VOCAB_SIZE
    return result

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()

def source_receipt(exported_program_dir: Path) -> dict[str, object]:
    exported = exported_program_dir / "exported.pt2"
    manifest = exported_program_dir / "manifest.json"
    if not exported.is_file() or not manifest.is_file():
        raise ValueError("frozen exported program requires exported.pt2 and manifest.json")
    return {
        "source_model_key": RC_WORKING_SOURCE_MODEL_KEY,
        "pipeline_alias": RC_WORKING_PIPELINE_ALIAS,
        "exported_program_sha256": sha256_file(exported),
        "export_manifest_sha256": sha256_file(manifest),
        "analyzer_sha256": sha256_file(Path(__file__)),
    }
~~~

The module must add the repository root to sys.path exactly as build_rc_working_reference.py does, then import only the fixed RC contract constants.

- [ ] **Step 4: Run the focused tests and syntax check**

Run: python -m unittest tests/test_rc_softmax_exp_domain.py -v && python -m py_compile scripts/pipeline/characterize_rc_softmax_exp_domain.py

Expected: PASS; no generated files outside the test temporary directory.

- [ ] **Step 5: Commit the deterministic contract**

~~~bash
git add scripts/pipeline/characterize_rc_softmax_exp_domain.py tests/test_rc_softmax_exp_domain.py
git commit -m "feat: define RC softmax domain contract"
~~~

### Task 2: Discover exact PT2E boundaries and observe values without rewriting the graph

**Files:**

- Modify: scripts/pipeline/characterize_rc_softmax_exp_domain.py
- Modify: tests/test_rc_softmax_exp_domain.py

**Interfaces:**

- Produces SoftmaxBoundary(node_name: str, dim: int, scale: float, zero_point: int, quant_min: int, quant_max: int, dtype: str).
- Produces discover_softmax_boundaries(graph_module: object) -> dict[str, SoftmaxBoundary].
- Produces f32_bit_words(tensor: object) -> set[int], derived_pre_exp_operand(value: object, dim: int) -> object, and ObservingInterpreter.
- Later tasks consume a per-site summary containing counts, extrema, and sorted f32 word sets.

- [ ] **Step 1: Add failing boundary and observer tests**

Use a torch.fx.symbolic_trace fixture containing two softmax calls. The test fixture must build a direct quantize/dequantize pair for each Softmax. Assert this public behavior:

~~~python
def test_discovers_two_immediate_affine_quantized_softmax_boundaries() -> None:
    boundaries = module.discover_softmax_boundaries(graph_module)
    self.assertEqual(set(boundaries), {"softmax", "softmax_1"})
    for boundary in boundaries.values():
        self.assertEqual(boundary.dim, -1)
        self.assertEqual(boundary.scale, 2.0 ** -12)
        self.assertEqual(boundary.zero_point, -124)
        self.assertEqual((boundary.quant_min, boundary.quant_max), (-128, 127))
        self.assertEqual(boundary.dtype, "torch.int8")

def test_rejects_softmax_without_an_immediate_matching_quantize_dequantize_pair() -> None:
    with self.assertRaisesRegex(ValueError, "immediate.*dequantize"):
        module.discover_softmax_boundaries(unquantized_graph_module)

def test_observer_forwards_original_result_and_records_stable_operand_bits() -> None:
    interpreter = module.ObservingInterpreter(graph_module, boundaries)
    input_tensor = torch.tensor([[[-0.5, 0.25]]], dtype=torch.float32)
    torch.testing.assert_close(interpreter.run(input_tensor), graph_module(input_tensor))
    summary = interpreter.summaries()["softmax"]
    self.assertEqual(summary["input_value_count"], 2)
    self.assertEqual(summary["derived_pre_exp_value_count"], 2)
    self.assertEqual(summary["derived_pre_exp_positive_count"], 0)
    self.assertIn(module.f32_word(0.0), summary["derived_pre_exp_bits"])
    self.assertIn(module.f32_word(-0.75), summary["derived_pre_exp_bits"])
~~~

- [ ] **Step 2: Run the tests to verify the discovery and observer code is absent**

Run: python -m unittest tests/test_rc_softmax_exp_domain.py -v

Expected: FAIL with missing SoftmaxBoundary, discover_softmax_boundaries, or ObservingInterpreter.

- [ ] **Step 3: Implement strict boundary discovery and a forwarding observer**

~~~python
@dataclass(frozen=True)
class SoftmaxBoundary:
    node_name: str
    dim: int
    scale: float
    zero_point: int
    quant_min: int
    quant_max: int
    dtype: str

def derived_pre_exp_operand(value: object, dim: int) -> object:
    import torch
    if value.dtype != torch.float32:
        raise ValueError(f"Softmax input must be f32, got {value.dtype}")
    return value - torch.amax(value, dim=dim, keepdim=True)

def f32_bit_words(tensor: object) -> set[int]:
    import torch
    if tensor.dtype != torch.float32:
        raise ValueError("bit accounting accepts f32 tensors only")
    words = tensor.detach().contiguous().cpu().view(torch.int32).reshape(-1).tolist()
    return {int(word) & 0xFFFFFFFF for word in words}

class ObservingInterpreter(torch.fx.Interpreter):
    def __init__(self, graph_module: object, boundaries: dict[str, SoftmaxBoundary]) -> None:
        super().__init__(graph_module)
        self.boundaries = boundaries
        self._current_node_name: str | None = None
        self._accumulators = {name: SiteAccumulator(boundary) for name, boundary in boundaries.items()}

    def run_node(self, node: object) -> object:
        self._current_node_name = node.name
        return super().run_node(node)

    def call_function(self, target: object, args: tuple[object, ...], kwargs: dict[str, object]) -> object:
        boundary = self.boundaries.get(self._current_node_name or "")
        if boundary is not None:
            self._accumulators[boundary.node_name].observe(args[0])
        return super().call_function(target, args, kwargs)
~~~

Discovery must inspect exact FX nodes; require aten.softmax.int, an immediate quantized_decomposed.dequantize_per_tensor.default argument, an immediate quantized_decomposed.quantize_per_tensor.default source, matching affine parameter tuples, and exactly the two expected signed-int8 boundaries. SiteAccumulator.observe must update finite/NaN/infinity counts, positive derived-value count, finite extrema, and exact f32 words. It must reject more than 256 words at either site.

- [ ] **Step 4: Run the observer tests and actual frozen-graph discovery probe**

Run:

~~~bash
python -m unittest tests/test_rc_softmax_exp_domain.py -v
nix develop .#default -c python scripts/pipeline/characterize_rc_softmax_exp_domain.py inspect --exported-program-dir "$(nix build .#tinystories-w8a8-rc-study-mask9-vocab6-width2-pytorch-exported --no-link --print-out-paths)"
~~~

Expected: tests PASS; inspection reports softmax and softmax_1, f32, 2^-12, -124, and [-128, 127], without writing a model or compiler artifact.

- [ ] **Step 5: Commit the read-only observer**

~~~bash
git add scripts/pipeline/characterize_rc_softmax_exp_domain.py tests/test_rc_softmax_exp_domain.py
git commit -m "feat: observe frozen RC softmax exponent inputs"
~~~

### Task 3: Add auditable shards, semantic reducer, and command-line interface

**Files:**

- Modify: scripts/pipeline/characterize_rc_softmax_exp_domain.py
- Modify: tests/test_rc_softmax_exp_domain.py

**Interfaces:**

- Produces characterize_shard(exported_program_dir: Path, start: int, stop: int) -> dict[str, object].
- Produces merge_shards(shards: list[dict[str, object]]) -> dict[str, object].
- CLI commands are inspect, characterize, and merge. characterize --out writes one shard JSON; merge --shard path --out writes one complete manifest.

- [ ] **Step 1: Write failing shard and merge tests**

~~~python
def test_merge_requires_adjacent_compatible_complete_coverage() -> None:
    first = module.synthetic_shard(start=0, stop=3, total=6**8, bit_words={0, 0xBF400000})
    second = module.synthetic_shard(start=3, stop=6**8, total=6**8, bit_words={0})
    merged = module.merge_shards([second, first])
    self.assertEqual(merged["coverage"], {"start": 0, "stop": 6**8, "complete": True})
    self.assertEqual(merged["sites"]["softmax"]["derived_pre_exp_bits"], ["0x00000000", "0xBF400000"])

def test_merge_rejects_gap_overlap_and_receipt_mismatch() -> None:
    first = module.synthetic_shard(start=0, stop=3, total=6**8, bit_words={0})
    gap = module.synthetic_shard(start=4, stop=6**8, total=6**8, bit_words={0})
    overlap = module.synthetic_shard(start=2, stop=6**8, total=6**8, bit_words={0})
    changed = module.synthetic_shard(start=3, stop=6**8, total=6**8, bit_words={0}, analyzer_sha="f" * 64)
    for candidate in ([first, gap], [first, overlap], [first, changed]):
        with self.assertRaisesRegex(ValueError, "coverage|receipt"):
            module.merge_shards(candidate)
~~~

- [ ] **Step 2: Run the tests to verify shard support fails before implementation**

Run: python -m unittest tests/test_rc_softmax_exp_domain.py -v

Expected: FAIL with missing merge_shards or shard-builder support.

- [ ] **Step 3: Implement the shard runner and reducer**

The shard JSON must contain schema_version 1, kind softmax-exp-domain-shard, receipt, enumeration (radix 6, context_length 8, total_contexts 1679616, start, stop), sites, and metrics. Each site must retain input_value_count, derived_pre_exp_value_count, finite/nan/infinity counts, derived_pre_exp_positive_count, finite minima/maxima, input_bits, derived_pre_exp_bits, runtime shape and dtype, and its affine boundary. Serialize words as zero-padded hexadecimal strings such as 0x00000000.

characterize_shard must load torch.export.load(exported_program_dir / "exported.pt2").module() once, run under torch.inference_mode(), construct torch.tensor([context_from_index(index)], dtype=torch.long), and execute the forwarding interpreter for every index. It must retain no tensor after SiteAccumulator.observe returns.

merge_shards must require matching receipts and boundary metadata, sort by start, require every next start equals the prior stop, require full [0, 1679616) coverage, sum counts, union words, recheck the 256-word bound, and set coverage.complete only after validation. Metrics are nonsemantic and must not affect a deterministic value comparison.

- [ ] **Step 4: Run unit tests plus a four-context local CLI smoke**

Run:

~~~bash
python -m unittest tests/test_rc_softmax_exp_domain.py -v
exported="$(nix build .#tinystories-w8a8-rc-study-mask9-vocab6-width2-pytorch-exported --no-link --print-out-paths)"
nix develop .#default -c python scripts/pipeline/characterize_rc_softmax_exp_domain.py characterize --exported-program-dir "$exported" --start 0 --stop 4 --out /tmp/rc-softmax-exp-smoke.json
~~~

Expected: all tests PASS; the smoke shard reports two sites and no positive derived-pre-exp values. The incomplete one-shard smoke is intentionally rejected by merge. This /tmp output is disposable; durable runs happen only in Nix outputs.

- [ ] **Step 5: Commit the shard and reducer interface**

~~~bash
git add scripts/pipeline/characterize_rc_softmax_exp_domain.py tests/test_rc_softmax_exp_domain.py
git commit -m "feat: package RC softmax domain shards"
~~~

### Task 4: Package pilot and exhaustive runs as stable Nix derivations

**Files:**

- Modify: flake.nix
- Create: tests/test_rc_softmax_exp_domain_nix.py

**Interfaces:**

- Produces .#tinystories-w8a8-rc-softmax-exp-domain-pilot containing first.json, repeat.json, semantic-determinism.json, and inspection.json.
- Produces .#tinystories-w8a8-rc-softmax-exp-domain-exhaustive containing full.shard.json and summary.json with complete coverage.

- [ ] **Step 1: Write failing Nix-wiring assertions**

~~~python
def test_flake_exposes_pilot_and_exhaustive_domain_derivations() -> None:
    flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
    self.assertIn('"tinystories-w8a8-rc-softmax-exp-domain-pilot"', flake)
    self.assertIn('"tinystories-w8a8-rc-softmax-exp-domain-exhaustive"', flake)
    self.assertIn("characterize_rc_softmax_exp_domain.py", flake)
    self.assertIn("--start 0 --stop 4", flake)
    self.assertIn("--start 0 --stop 1679616", flake)
    self.assertIn("semantic-determinism.json", flake)
~~~

- [ ] **Step 2: Run the wiring test to verify it fails**

Run: python -m unittest tests/test_rc_softmax_exp_domain_nix.py -v

Expected: FAIL because neither package name nor runner invocation exists in flake.nix.

- [ ] **Step 3: Add the two derivations next to quantizedRcNonlinearSlices**

The pilot derivation must run characterize twice over [0, 4), remove .metrics through jq -S del(.metrics), compare semantic JSON through cmp, retain both original reports, and write semantic-determinism.json. The exhaustive derivation must run [0, 1679616), invoke merge on the complete shard, then require jq -e '.coverage.complete == true and .coverage.start == 0 and .coverage.stop == 1679616' on summary.json.

Both derivations must use pythonWithTinyStoriesTorchAO, export PYTHONPATH to the source root, use set -euo pipefail, and write only under $out. Expose the exact two package aliases in the packages set.

- [ ] **Step 4: Validate Nix syntax and build the inexpensive pilot**

Run:

~~~bash
python -m unittest tests/test_rc_softmax_exp_domain_nix.py -v
nix flake check -L
nix build .#tinystories-w8a8-rc-softmax-exp-domain-pilot -L --no-link --print-out-paths
~~~

Expected: wiring test and flake check PASS; pilot output contains repeatable semantic reports and observed throughput without making a lowering claim.

- [ ] **Step 5: Commit the Nix evidence route**

~~~bash
git add flake.nix tests/test_rc_softmax_exp_domain_nix.py
git commit -m "build: package RC softmax domain analysis"
~~~

### Task 5: Run exhaustive evidence and publish a bounded result

**Files:**

- Create: docs/results/2026-07-17-rc-softmax-exp-domain.md
- Create: tests/test_rc_softmax_exp_domain_result.py

**Interfaces:**

- Consumes the Nix pilot first.json and exhaustive summary.json.
- Produces a checked-in result document that names source hashes, coverage, actual bit domains, f32 numeric range, finite/special counts, and measured performance.

- [ ] **Step 1: Write the failing trust-boundary test for the result document**

~~~python
def test_result_states_read_only_analysis_and_no_equivalence_claim() -> None:
    result = (ROOT / "docs/results/2026-07-17-rc-softmax-exp-domain.md").read_text(encoding="utf-8")
    self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", result)
    self.assertIn("derived_pre_exp_operand", result)
    self.assertIn("read-only", result.lower())
    self.assertIn("not functional-equivalence evidence", result)
    self.assertNotIn("SV equivalence proved", result)
    self.assertNotIn("math.exp is exact", result.lower())
~~~

- [ ] **Step 2: Run it to verify the unpublished result fails**

Run: python -m unittest tests/test_rc_softmax_exp_domain_result.py -v

Expected: FAIL with FileNotFoundError.

- [ ] **Step 3: Build and inspect the full exhaustive derivation without an artificial scout cutoff**

Run:

~~~bash
nix build .#tinystories-w8a8-rc-softmax-exp-domain-exhaustive -L --no-link --print-out-paths
~~~

After completion, inspect receipt, coverage, every site input_bits and derived_pre_exp_bits, value/special counts, and metrics with jq; compute SHA-256 of full.shard.json and summary.json. If a genuine resource or time boundary stops the run, preserve the build log and record its exact command, measured pilot, attempted full execution, and limiting resource. Do not replace complete coverage with an inference from quantization bounds.

- [ ] **Step 4: Publish the actual bounded result and run all relevant tests**

The result document must have headings Frozen input and method, Pilot, Exhaustive coverage, Observed domains, Interpretation, and Limits and next decision. It must distinguish raw aten.softmax.int inputs from analysis-only derived_pre_exp_operand, state whether every observed value was finite and nonpositive after maximum subtraction, and say the result informs future exponent-candidate range requirements only.

Run:

~~~bash
python -m unittest tests/test_rc_softmax_exp_domain.py tests/test_rc_softmax_exp_domain_nix.py tests/test_rc_softmax_exp_domain_result.py -v
git diff --check
~~~

Expected: PASS and no whitespace errors.

- [ ] **Step 5: Commit the result and verify a clean worktree**

~~~bash
git add docs/results/2026-07-17-rc-softmax-exp-domain.md tests/test_rc_softmax_exp_domain_result.py
git commit -m "docs: record RC softmax exponent domain"
git status --short
~~~

Expected: no output from git status --short.

