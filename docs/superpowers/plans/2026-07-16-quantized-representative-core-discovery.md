# Quantized Representative-Core Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reproducible PT2E W8A8 TinyStories representative-core sweep that selects only structure- and speed-qualified candidates at the Torch-MLIR boundary.

**Architecture:** A clean, configuration-scaled GPT-Neo adapter supplies full-model and reduced-core PT2E W8A8 exports from the same frozen eight-token structural input. A measured Torch-MLIR derivation records elapsed lowering time and MLIR size. A generic fingerprint derives operator, normalized type-signature, and producer-to-consumer-edge coverage from each Torch-MLIR artifact, and a qualifier selects candidates only when they cover the full model and meet the agreed size/time gates.

**Tech Stack:** Python 3 standard library, PyTorch/PT2E XNNPACK quantization, Transformers GPT-Neo, Torch-MLIR, Nix.

## Global Constraints

- Preserve the old `tinystories-w8a8` zero-token scout and all historical W4A8 cores; do not relabel them as valid representative cores.
- Full PT2E W8A8 uses pretrained TinyStories weights. RCs use only `AutoModelForCausalLM.from_config` with scaled configuration; they must not replace native embeddings, attention, LayerNorm, GELU, or residuals.
- Use one checked-in static context of exactly eight token positions. Its RC mapping preserves equality, repetition, ordering, and positions but is explicitly structural calibration, not a language-quality claim.
- Initial study stops at Torch-MLIR. Its report must say that it makes no RTLIL/SV/LUT/FF/BRAM/DSP claim.
- A candidate must contain all full-model normalized operation signatures and all full-model producer-to-consumer operation edges.
- A candidate is eligible only when lowering is at least `10x` faster and serialized Torch-MLIR is at most `0.10x` the full artifact; `100x` is reported as the preferred operational target.
- Implement PT2E W8A8 first. SmoothQuant is a later profile using the same measurement and qualification interface; do not claim it is implemented by this change.
- Do not commit unless the user explicitly asks during this implementation.

---

### Task 1: Add the clean PT2E W8A8 study adapters and frozen structural input

**Files:**
- Create: `TinyStories/quantized_rc_study_input.json`
- Create: `TinyStories/quantized_rc_study_input.py`
- Create: `TinyStories/pt2e_w8a8_study.py`
- Create: `TinyStories/model_adapter_pt2e_w8a8_study.py`
- Create: `TinyStories/model_adapter_quantized_representative_core_pt2e_w8a8.py`
- Test: `tests/test_quantized_representative_core_study.py`

**Interfaces:**
- `pt2e_w8a8_study.load_full_token_ids() -> tuple[int, ...]` returns exactly eight checked-in full-vocabulary IDs.
- `pt2e_w8a8_study.map_token_ids_to_vocab(ids: tuple[int, ...], vocab_size: int) -> tuple[int, ...]` assigns compact IDs in first-occurrence order and fails if `vocab_size` is too small.
- `pt2e_w8a8_study.export_pt2e_w8a8(model, example_inputs, calibration_inputs) -> torch.export.ExportedProgram` performs standard static XNNPACK W8A8 conversion.
- Both adapters expose `export_program(model_path)` and preserve a rank-two `int64` `[1, 8]` token input.

- [x] **Step 1: Write failing adapter-contract tests**

```python
def test_clean_rc_adapter_has_no_hardware_semantic_substitutions(self):
    source = STUDY_RC_ADAPTER.read_text(encoding="utf-8")
    for forbidden in (
        "Int8Embedding", "FixedPointLayerNormBridge",
        "QuadraticGeluHardwareApproximation",
        "replace_attention_with_hardware_friendly_attention",
    ):
        self.assertNotIn(forbidden, source)

def test_structural_input_is_eight_positions_and_mapping_preserves_repetition(self):
    fixture = json.loads(STUDY_INPUT.read_text(encoding="utf-8"))
    self.assertEqual(fixture["context_length"], 8)
    self.assertEqual(len(fixture["full_token_ids"]), 8)
    self.assertEqual(fixture["full_token_ids"][1], fixture["full_token_ids"][4])
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests/test_quantized_representative_core_study.py -v`

Expected: FAIL because the study files do not exist.

- [x] **Step 3: Implement the shared adapter helpers and clean adapters**

```python
def map_token_ids_to_vocab(ids: tuple[int, ...], vocab_size: int) -> tuple[int, ...]:
    mapping: dict[int, int] = {}
    mapped: list[int] = []
    for token_id in ids:
        if token_id not in mapping:
            mapping[token_id] = len(mapping)
        mapped.append(mapping[token_id])
    if len(mapping) > vocab_size:
        raise ValueError("RC vocabulary cannot represent frozen token equality classes")
    return tuple(mapped)
```

The full adapter loads pretrained weights with `attn_implementation="eager"`; the RC adapter loads the same configuration class, changes only vocabulary/layer/position/window/hidden/head fields, reconstructs `attention_types`, seeds model construction deterministically, and uses no model rewrite.

- [x] **Step 4: Run adapter-contract tests**

Run: `python3 -m unittest tests/test_quantized_representative_core_study.py -v`

Expected: PASS.

### Task 2: Implement mechanically derived Torch-MLIR fingerprints and qualification

**Files:**
- Create: `scripts/pipeline/torch_mlir_fingerprint.py`
- Create: `scripts/pipeline/qualify_quantized_representative_core.py`
- Test: `tests/test_torch_mlir_fingerprint.py`

**Interfaces:**
- `torch_mlir_fingerprint.py --input MODEL.mlir --label LABEL --out FINGERPRINT.json` writes operation names, normalized operation signatures, and directed producer-operation-to-consumer-operation edges.
- `qualify_quantized_representative_core.py --baseline BASE.json --candidate RC.json --baseline-metrics BASE.metrics.json --candidate-metrics RC.metrics.json --out REPORT.json --markdown-out REPORT.md` writes a pass/fail qualification decision.

- [x] **Step 1: Write failing fingerprint and qualification tests**

```python
def test_fingerprint_records_normalized_op_signatures_and_edges(self):
    payload = run_fingerprint('''
      %0 = "torch.foo"() : () -> !torch.vtensor<[1,8,64],f32>
      %1 = "torch.bar"(%0) : (!torch.vtensor<[1,8,64],f32>) -> !torch.vtensor<[1,8,64],f32>
    ''')
    self.assertIn("torch.foo", payload["operation_names"])
    self.assertIn("torch.foo -> torch.bar", payload["producer_consumer_edges"])
    self.assertIn("!torch.vtensor<[?,?,?],f32>", payload["normalized_type_text"])

def test_qualification_rejects_missing_edge_even_when_ops_exist(self):
    report = qualify(baseline_with_edge, candidate_without_edge, 1_000, 50, 10_000, 500)
    self.assertFalse(report["eligible"])
    self.assertIn("missing_producer_consumer_edges", report["failure_reasons"])
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests/test_torch_mlir_fingerprint.py -v`

Expected: FAIL because the two scripts do not exist.

- [x] **Step 3: Implement a conservative textual fingerprint**

The parser must derive every set from the full input rather than a curated operator list. Normalize only integer dimensions inside tensor/vector shape brackets to `?`; retain operation names, ranks, element types, and all producer-to-consumer operation pairs. The qualifier must use exact set inclusion for signatures and edges and emit missing entries in JSON/Markdown.

```python
eligible = (
    not missing_operation_signatures
    and not missing_producer_consumer_edges
    and candidate_elapsed_ns * 10 <= baseline_elapsed_ns
    and candidate_mlir_bytes * 10 <= baseline_mlir_bytes
)
```

- [x] **Step 4: Run the new tests**

Run: `python3 -m unittest tests/test_torch_mlir_fingerprint.py -v`

Expected: PASS.

### Task 3: Wire a bounded PT2E W8A8 study matrix into Nix

**Files:**
- Modify: `nix/models.nix`
- Modify: `flake.nix`
- Create: `scripts/pipeline/write_torch_mlir_study_metrics.py`
- Test: `tests/test_quantized_representative_core_study.py`

**Interfaces:**
- Register one new pretrained full-model profile `tinystories-w8a8-rc-study-full` and a staged grid of clean RC configurations, all with context length eight.
- Expose `nix build .#tinystories-w8a8-rc-study` which writes `summary.json`, `summary.md`, full and candidate fingerprints, metrics, and individual qualification reports.
- Each measured stage directory contains `model.torch.mlir`, `metrics.json`, and `fingerprint.json`.

- [x] **Step 1: Write failing Nix/static-contract tests**

```python
def test_flake_exposes_pt2e_rc_study_without_claiming_fpga_utilization(self):
    flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
    self.assertIn('"tinystories-w8a8-rc-study"', flake)
    self.assertIn("qualify_quantized_representative_core.py", flake)
    self.assertNotIn("rc-study-xc7", flake)

def test_nix_rc_profiles_use_the_clean_w8a8_study_adapter(self):
    models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")
    self.assertIn("model_adapter_quantized_representative_core_pt2e_w8a8.py", models)
    self.assertIn("TINYSTORIES_RC_STUDY_CONTEXT_LENGTH=8", models)
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests/test_quantized_representative_core_study.py -v`

Expected: FAIL because neither the models nor the flake expose the study.

- [x] **Step 3: Add bounded profiles and measured derivations**

Use independent axis rungs: an anchor with `vocab=32,layers=2,context=8,window=4,hidden=4,heads=1`; vocabulary rungs at 128 and 512; width/head rungs `(8,2)` and `(16,4)`; a four-layer rung; an eight-position local-window rung; and a full-mask-configuration rung with `max_position_embeddings=2048,window=256`. The last rung tests whether preserving GPT-Neo's non-folded causal-mask structure is necessary. The aggregator must select no candidate when none passes; it must never choose the historical W4A8 adapters.

```nix
mkMeasuredTorchMlirStage = { name, exportedProgram }:
  pkgs.runCommand "${name}-torch-mlir-study" { buildInputs = [ pythonWithTinyStoriesTorchAO torchMlir ]; } ''
    mkdir -p "$out"
    start_ns="$(date +%s%N)"
    python ${./scripts/compile-pytorch.py} --exported-program-dir ${exportedProgram} --out "$out/model.torch.mlir" >/dev/null
    elapsed_ns="$(( $(date +%s%N) - start_ns ))"
    python ${./scripts/pipeline/write_torch_mlir_study_metrics.py} --mlir "$out/model.torch.mlir" --elapsed-ns "$elapsed_ns" --out "$out/metrics.json"
  '';
```

- [x] **Step 4: Run static tests and evaluate the new output**

Run: `python3 -m unittest tests/test_quantized_representative_core_study.py -v && nix eval .#tinystories-w8a8-rc-study --raw`

Expected: tests PASS and evaluation resolves a store derivation.

### Task 4: Build the study, record the selection result, and document its scope

**Files:**
- Create: `docs/adr/2026-07-16-quantized-representative-core-study.md`
- Create: `docs/results/2026-07-16-quantized-representative-core-pt2e-w8a8.md`
- Test: `tests/test_quantized_representative_core_study.py`

**Interfaces:**
- The result report quotes the generated `summary.json` rather than hand-copying metrics.
- It records full/candidate artifact identifiers, coverage result, time/size ratios, selected candidate or `none`, and explicitly defers SmoothQuant, equivalence, downstream lowering, and FPGA resource claims.

- [x] **Step 1: Build the bounded study**

Run: `nix build .#tinystories-w8a8-rc-study -L --no-link --print-out-paths`

Expected: one persistent Nix output directory containing the complete report bundle.

- [x] **Step 2: Write the result report from generated evidence**

The report must distinguish “coverage-valid candidate” from “resource-predictive RC,” which remains unproven until a finalist and the full model complete a later identical downstream lowering.

- [x] **Step 3: Run complete validation**

Run: `python3 -m unittest discover -s tests -v && nix flake check -L`

Expected: repository tests PASS; flake check passes or any unrelated pre-existing failure is reported separately.

## Plan Self-Review

- Coverage: Tasks 1–3 implement the frozen eight-token PT2E W8A8 full/RC study, mechanical coverage audit, speed/size gates, and Nix reproducibility. Task 4 records either a selected candidate or a valid negative result.
- No placeholders: every file, command, threshold, and public output name is specified.
- Consistency: all qualification paths consume `fingerprint.json` plus `metrics.json`; no task reaches TOSA, RTLIL, SV, or FPGA mapping.
