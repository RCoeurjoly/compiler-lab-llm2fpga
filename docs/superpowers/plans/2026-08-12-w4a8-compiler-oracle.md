# W4A8 Compiler Oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a frozen, functionally validated, Nix-reproducible W4A8 compiler-generated RTL oracle and its mapped XC7K480T synthesis/P&R baseline.

**Architecture:** Add a dedicated W4A8 sibling of the existing stateful serving system rather than changing the accepted W8A8 artifacts. Freeze the quantized arithmetic and tensor layout in one manifest, lower the three serving phases through the current compiler route, reuse the established latency-insensitive observable test interface, and package every verification and implementation result as a Nix artifact.

**Tech Stack:** Python 3, PyTorch/PT2E and TorchAO, torch.export, Torch-MLIR/CIRCT/Calyx, SystemVerilog, Verilator, Yosys/Slang, nextpnr-xilinx/openXC7, Nix, `unittest`.

## Global Constraints

- Target exactly `xc7k480tffg1156-1` using `xc7k480tffg1156.bin`.
- Keep the existing W8A8 oracle and synthesis artifacts immutable; W4A8 uses new model keys and derivations.
- Preserve the external serving geometry: vocabulary 6, two layers, hidden size 2, one head, prompt length 8, and two decode steps.
- W4 weights are signed two's-complement values in `[-8, 7]`; activations remain signed A8 in `[-128, 127]`.
- A single versioned manifest defines quantization, tensor checksums, packing, rounding, saturation, accumulator bounds, and phase ABI.
- Authoritative artifacts must be Nix store outputs; `/tmp` is scratch only.
- Do not use `read_slang --ignore-initial` for the eventual initialized-memory fitting implementation. This compiler-oracle baseline must explicitly report whether its generated RTL contains or depends on ignored initialization.
- Do not claim a universal finite-domain result before all `6^8 = 1,679,616` legal contexts pass.
- Do not claim Fmax or critical paths unless nextpnr completes legal placement and routing.
- Preserve unrelated worktree changes in `TinyStories/rc_serving_direct_export.py` and `survey/`; inspect and integrate around the former rather than overwriting it.
- Do not import kev-gpt source until its precise GPL version and repository compatibility are recorded.

---

## File structure

- `TinyStories/rc_serving_w4a8_contract.py`: immutable W4A8 model key, arithmetic constants, phase ABI, and manifest validation.
- `TinyStories/rc_serving_w4a8_source.py`: deterministic source-model construction and phase invocation helpers.
- `TinyStories/rc_serving_w4a8_export.py`: per-phase PT2E W4A8 conversion, converted-graph tensor extraction, cross-phase deduplication, and manifest creation.
- `scripts/pipeline/materialize_rc_serving_w4a8.py`: command-line materializer only.
- `nix/rc-serving-w4a8-system.nix`: model, export, lowering, simulation, exhaustive verification, and synthesis derivations.
- `tests/test_rc_serving_w4a8_contract.py`: manifest and arithmetic contract tests.
- `tests/test_rc_serving_w4a8_export.py`: export and frozen-tensor tests.
- `tests/test_rc_serving_w4a8_nix.py`: static Nix wiring and durability tests.
- `tests/test_rc_serving_w4a8_equivalence.py`: report/parser and finite-domain scheduling tests.
- `docs/results/YYYY-MM-DD-rc-w4a8-compiler-oracle.md`: measured functional and implementation evidence.

### Task 1: Freeze the W4A8 arithmetic and artifact contract

**Files:**
- Create: `TinyStories/rc_serving_w4a8_contract.py`
- Create: `tests/test_rc_serving_w4a8_contract.py`

**Interfaces:**
- Consumes: phase geometry from `TinyStories.rc_serving_contract`.
- Produces: `W4A8_MODEL_KEY: str`, `QuantizedTensorRecord`, `W4A8Manifest`, `validate_manifest(payload: object) -> W4A8Manifest`, and `accumulator_bounds(reduction_length: int) -> tuple[int, int]`.

- [ ] **Step 1: Write failing contract tests**

```python
from TinyStories.rc_serving_w4a8_contract import (
    W4A8_MODEL_KEY, accumulator_bounds, validate_manifest,
)

def test_w4a8_contract_has_exact_ranges_and_accumulator_bound():
    assert W4A8_MODEL_KEY == "tinystories-w4a8-rc-serving-mask10-vocab6-width2"
    assert accumulator_bounds(2) == (-2032, 2048)

def test_manifest_rejects_wrong_packing_order():
    payload = valid_manifest_payload()
    payload["packing"]["nibble_order"] = "high-even-low-odd"
    with pytest.raises(ValueError, match="nibble_order"):
        validate_manifest(payload)
```

Include `valid_manifest_payload()` in the test with schema version 1, signed W4/A8 ranges, low-nibble-even packing, round-to-nearest-even, signed saturation, all three phase names, and one tensor with a 64-character SHA-256.

- [ ] **Step 2: Run the new test and confirm the missing-module failure**

Run: `python -m pytest tests/test_rc_serving_w4a8_contract.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'TinyStories.rc_serving_w4a8_contract'`.

- [ ] **Step 3: Implement the immutable contract**

Define frozen dataclasses and validate every literal rather than accepting arbitrary formats:

```python
W4A8_MODEL_KEY = "tinystories-w4a8-rc-serving-mask10-vocab6-width2"
WEIGHT_BITS, WEIGHT_MIN, WEIGHT_MAX = 4, -8, 7
ACTIVATION_BITS, ACTIVATION_MIN, ACTIVATION_MAX = 8, -128, 127
NIBBLE_ORDER = "low-even-high-odd"
ROUNDING_MODE = "round-to-nearest-even"
SATURATION_MODE = "signed-clamp"

def accumulator_bounds(reduction_length: int) -> tuple[int, int]:
    if reduction_length <= 0:
        raise ValueError("reduction_length must be positive")
    products = (WEIGHT_MIN * ACTIVATION_MAX,
                WEIGHT_MIN * ACTIVATION_MIN,
                WEIGHT_MAX * ACTIVATION_MAX,
                WEIGHT_MAX * ACTIVATION_MIN)
    return reduction_length * min(products), reduction_length * max(products)
```

Require canonical phase order `prefill-8`, `decode-8`, `decode-9`, unique tensor names, positive dimensions, exact byte counts, and lowercase SHA-256 strings.

- [ ] **Step 4: Run focused and existing serving-contract tests**

Run: `python -m pytest tests/test_rc_serving_w4a8_contract.py tests/test_rc_serving_contract.py -q`

Expected: all tests PASS.

- [ ] **Step 5: Commit the contract**

```bash
git add TinyStories/rc_serving_w4a8_contract.py tests/test_rc_serving_w4a8_contract.py
git commit -m "feat: freeze RC W4A8 arithmetic contract"
```

### Task 2: Convert deterministic serving phases to W4A8 and freeze their tensors

**Files:**
- Create: `TinyStories/rc_serving_w4a8_source.py`
- Create: `TinyStories/rc_serving_w4a8_export.py`
- Create: `scripts/pipeline/materialize_rc_serving_w4a8.py`
- Create: `tests/test_rc_serving_w4a8_export.py`
- Read/coordinate: `TinyStories/rc_serving_direct_export.py` (user-modified; do not replace)

**Interfaces:**
- Consumes: `W4A8Manifest` and existing `ServingTrace`.
- Produces: `build_w4a8_source_model(model_path: Path) -> torch.nn.Module`, `convert_w4a8_phase(model, invocation) -> torch.export.ExportedProgram`, `quantized_tensor_records(exported_phases) -> tuple[QuantizedTensorRecord, ...]`, and `materialize_w4a8_bundle(model_path, trace_path, out_dir) -> None`.

- [ ] **Step 1: Test deterministic tensors and phase outputs**

```python
def test_w4a8_materialization_is_byte_deterministic(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    monkeypatch.setattr(export, "build_w4a8_source_model", fake_model)
    export.materialize_w4a8_bundle(Path("checkpoint"), TRACE, first)
    export.materialize_w4a8_bundle(Path("checkpoint"), TRACE, second)
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    assert (first / "weights.bin").read_bytes() == (second / "weights.bin").read_bytes()

def test_every_weight_is_signed_int4():
    records = export.quantized_tensor_records(fake_converted_phases())
    assert records
    assert all(record.bits == 4 and record.signed for record in records)
```

The fake converted programs must expose graph-referenced integer weight
constants containing boundary values `-8`, `-1`, `0`, and `7`, plus one
out-of-range case that expects `ValueError` rather than silent clipping. Add a
second phase containing the same weight bytes and assert that the bundle stores
one deduplicated tensor with both phase references.

- [ ] **Step 2: Confirm the new tests fail**

Run: `python -m pytest tests/test_rc_serving_w4a8_export.py -q`

Expected: FAIL because `rc_serving_w4a8_source` and `rc_serving_w4a8_export` do not exist.

- [ ] **Step 3: Implement quantization and deterministic materialization**

Build the deterministic FP source model, export each phase with its native cache
inputs, then prepare, calibrate, and convert that exported phase using the PT2E
static quantizer with:

```python
os.environ["TINYSTORIES_PYTORCHAO_WEIGHT_BITS"] = "4"
os.environ["TINYSTORIES_PYTORCHAO_ACTIVATION_BITS"] = "8"
torch.manual_seed(0)
```

Extract only graph-referenced integer weight constants plus their scale and zero
point metadata from the converted programs. Do not infer weights from the FP
source model's `state_dict`. Deduplicate constants across phases by semantic
metadata and raw bytes, retaining all phase/node references in the manifest.
Pack adjacent signed nibbles as `(odd & 0xF) << 4 | (even & 0xF)`. Emit canonical
sorted JSON with a trailing newline, `weights.bin`, per-phase converted
`exported.pt2`, FP-source and converted logits, cache snapshots, and SHA-256s.
Reject tensors outside `[-8, 7]`.

- [ ] **Step 4: Run export and regression tests**

Run: `python -m pytest tests/test_rc_serving_w4a8_export.py tests/test_rc_serving_direct_export.py tests/test_rc_serving_reference.py -q`

Expected: all tests PASS; any pre-existing failure caused by the user-modified direct exporter must be reported before changing that file.

- [ ] **Step 5: Commit the W4A8 exporter**

```bash
git add TinyStories/rc_serving_w4a8_source.py TinyStories/rc_serving_w4a8_export.py scripts/pipeline/materialize_rc_serving_w4a8.py tests/test_rc_serving_w4a8_export.py
git commit -m "feat: export deterministic RC W4A8 bundle"
```

### Task 3: Package the frozen W4A8 bundle in Nix

**Files:**
- Create: `nix/rc-serving-w4a8-system.nix`
- Create: `tests/test_rc_serving_w4a8_nix.py`
- Modify: `flake.nix` at the `rcServingSystem` import and package export sections.

**Interfaces:**
- Consumes: `materialize_rc_serving_w4a8.py` and the pinned TinyStories snapshot.
- Produces packages ending in `-frozen-bundle`, `-prefill-8-pytorch-exported`, `-decode-8-pytorch-exported`, and `-decode-9-pytorch-exported`.

- [ ] **Step 1: Add failing Nix wiring assertions**

```python
KEY = "tinystories-w4a8-rc-serving-mask10-vocab6-width2"

def test_w4a8_system_is_dedicated_and_exported():
    system = (ROOT / "nix/rc-serving-w4a8-system.nix").read_text()
    flake = (ROOT / "flake.nix").read_text()
    assert 'schema_version = 1' in system
    assert '--out-dir "$out"' in system
    for suffix in ("frozen-bundle", "prefill-8-pytorch-exported",
                   "decode-8-pytorch-exported", "decode-9-pytorch-exported"):
        assert f'"{KEY}-{suffix}"' in flake
```

- [ ] **Step 2: Run and observe the missing-file failure**

Run: `python -m pytest tests/test_rc_serving_w4a8_nix.py -q`

Expected: FAIL with `FileNotFoundError` for `nix/rc-serving-w4a8-system.nix`.

- [ ] **Step 3: Add derivations and flake exports**

Mirror the dedicated structure of `nix/rc-serving-system.nix`, but emit the W4A8 model key, exact quantization metadata, frozen bundle, and phase symlinks. Build twice inside the bundle derivation and `cmp` the manifests and packed weights to enforce reproducibility.

- [ ] **Step 4: Evaluate and build the bundle**

Run:

```bash
python -m pytest tests/test_rc_serving_w4a8_nix.py -q
nix eval .#packages.x86_64-linux.tinystories-w4a8-rc-serving-mask10-vocab6-width2-frozen-bundle.name
nix build .#tinystories-w4a8-rc-serving-mask10-vocab6-width2-frozen-bundle --no-link --print-out-paths -L
```

Expected: tests PASS, evaluation returns the expected name, and the output contains nonempty `manifest.json`, `weights.bin`, and three phase directories.

- [ ] **Step 5: Commit the Nix bundle**

```bash
git add nix/rc-serving-w4a8-system.nix tests/test_rc_serving_w4a8_nix.py flake.nix
git commit -m "build: package frozen RC W4A8 oracle"
```

### Task 4: Lower all W4A8 serving phases through the current compiler

**Files:**
- Modify: `nix/rc-serving-w4a8-system.nix`
- Modify: `tests/test_rc_serving_w4a8_nix.py`

**Interfaces:**
- Consumes: three W4A8 `exported.pt2` artifacts.
- Produces: `generated-sv` bundles for each phase, including stage receipts, source hashes, top-module/interface inventory, and compressed logs.

- [ ] **Step 1: Require phase lowering packages and provenance**

Add assertions that the Nix source contains each phase name, invokes the same pinned pipeline functions as the passing W8A8 route, and writes `lowering-receipt.json`, `main.sv`, `interface.json`, and `sha256sums.txt`. Assert it does not reference a W8A8 store path or checked-in generated SV.

- [ ] **Step 2: Run the static test and verify failure**

Run: `python -m pytest tests/test_rc_serving_w4a8_nix.py -q`

Expected: FAIL because the generated-SV products are absent.

- [ ] **Step 3: Add one parameterized lowering function**

Implement `lowerPhase = { phase, exported }: ...` in Nix. It must reuse the current Torch-MLIR/CIRCT/Calyx path and synthesis normalizer without semantic RTL edits, retain every intermediate-stage receipt needed to diagnose failures, and expose three packages named `${W4A8_KEY}-${phase}-generated-sv`.

- [ ] **Step 4: Build phase RTL sequentially and inspect interfaces**

Run each package with `--no-link --print-out-paths -L`, redirecting any additional diagnostic output to a file. Expected: all builds exit 0, each has a nonempty `main.sv`, and `interface.json` matches the phase ABI in the manifest. If lowering fails, commit no workaround until the failing stage and operation are recorded.

- [ ] **Step 5: Commit compiler lowering**

```bash
git add nix/rc-serving-w4a8-system.nix tests/test_rc_serving_w4a8_nix.py flake.nix
git commit -m "feat: lower RC W4A8 serving phases to RTL"
```

### Task 5: Establish PyTorch-to-generated-RTL simulation gates

**Files:**
- Create: `tests/test_rc_serving_w4a8_equivalence.py`
- Create: `scripts/pipeline/run_rc_w4a8_equivalence.py`
- Modify: `nix/rc-serving-w4a8-system.nix`
- Modify: `flake.nix`

**Interfaces:**
- Consumes: frozen manifest, phase oracle records, and generated phase SV.
- Produces: `equivalence.json` with `status`, `suite`, `contexts_tested`, `first_mismatch`, hashes, simulator runtime, peak RSS, and cycles.

- [ ] **Step 1: Test strict comparison and ordered-reset scheduling**

```python
def test_compare_requires_all_six_raw_logits():
    expected = {"logits": [-2, 3, 3, 0, -1, 1], "argmax": 1}
    actual = {"logits": [-2, 3, 3, 0, -1, 1], "argmax": 1}
    assert compare_result(expected, actual) is None
    actual["logits"][5] = 0
    assert compare_result(expected, actual)["field"] == "logits[5]"

def test_ordered_reset_suite_resets_between_contexts():
    events = list(ordered_reset_events([[0] * 8, [1] * 8]))
    assert [event.kind for event in events] == [
        "reset", "request", "result", "reset", "request", "result"
    ]
```

- [ ] **Step 2: Run and confirm missing implementation failure**

Run: `python -m pytest tests/test_rc_serving_w4a8_equivalence.py -q`

Expected: FAIL importing `run_rc_w4a8_equivalence`.

- [ ] **Step 3: Implement the Verilator driver and report writer**

Adapt the established RC observable driver, but take paths and ABI exclusively from the W4A8 manifest. Compare all six signed raw logits before argmax; apply lowest-index tie breaking; bound every transaction using a manifest-recorded maximum cycle count; record timeout as failure. Implement suites `context-0`, `frozen-four`, and `ordered-reset`.

- [ ] **Step 4: Run unit and Nix simulation gates**

Run:

```bash
python -m pytest tests/test_rc_serving_w4a8_equivalence.py tests/test_rc_observable_driver.py tests/test_rc_sv_equivalence_fixture.py -q
nix build .#tinystories-w4a8-rc-serving-mask10-vocab6-width2-context0-equivalence --no-link -L
nix build .#tinystories-w4a8-rc-serving-mask10-vocab6-width2-frozen-four-equivalence --no-link -L
nix build .#tinystories-w4a8-rc-serving-mask10-vocab6-width2-ordered-reset-equivalence --no-link -L
```

Expected: all tests and builds PASS with exact logits and argmax.

- [ ] **Step 5: Commit simulation equivalence**

```bash
git add scripts/pipeline/run_rc_w4a8_equivalence.py tests/test_rc_serving_w4a8_equivalence.py nix/rc-serving-w4a8-system.nix flake.nix
git commit -m "test: validate compiler RC W4A8 RTL"
```

### Task 6: Add resumable exhaustive finite-domain verification

**Files:**
- Modify: `scripts/pipeline/run_rc_w4a8_equivalence.py`
- Modify: `tests/test_rc_serving_w4a8_equivalence.py`
- Modify: `nix/rc-serving-w4a8-system.nix`
- Modify: `flake.nix`

**Interfaces:**
- Consumes: an inclusive-exclusive base-six context interval.
- Produces: deterministic shard receipts and a merger that accepts exactly one complete, disjoint cover of `[0, 6**8)`.

- [ ] **Step 1: Test base-six indexing and strict shard coverage**

```python
def test_context_index_round_trip_at_boundaries():
    assert index_to_context(0) == (0,) * 8
    assert index_to_context(6**8 - 1) == (5,) * 8

def test_merge_rejects_gap_or_overlap():
    with pytest.raises(ValueError, match="complete disjoint cover"):
        merge_shards([receipt(0, 100), receipt(99, 6**8)])
```

- [ ] **Step 2: Run the focused tests and see missing symbols**

Run: `python -m pytest tests/test_rc_serving_w4a8_equivalence.py -q`

Expected: FAIL for undefined `index_to_context` and `merge_shards`.

- [ ] **Step 3: Implement deterministic shards and merger**

Use half-open intervals, fixed-width base-six conversion, per-shard first-mismatch evidence, and a merger that verifies identical model/SV/manifest hashes, sorts by start index, rejects gaps/overlaps, and requires final end `1_679_616` before returning `status: pass`.

- [ ] **Step 4: Run a two-shard smoke then the exhaustive Nix build**

Run the unit test, two small adjacent manual shards, and the Nix exhaustive package. Expected: small shards merge; the authoritative build tests exactly 1,679,616 contexts. Because this may be long-running, logs go to the derivation and progress is reported through Nix, not `/tmp` alone.

- [ ] **Step 5: Commit exhaustive verification**

```bash
git add scripts/pipeline/run_rc_w4a8_equivalence.py tests/test_rc_serving_w4a8_equivalence.py nix/rc-serving-w4a8-system.nix flake.nix
git commit -m "test: exhaustively verify RC W4A8 contexts"
```

### Task 7: Run mapped Yosys and nextpnr as a durable baseline

**Files:**
- Create: `nix/rc-w4a8-synthesis-baseline.nix`
- Modify: `tests/test_rc_serving_w4a8_nix.py`
- Modify: `flake.nix`

**Interfaces:**
- Consumes: validated generated W4A8 synthesis closure.
- Produces: normalized SV, mapped JSON/statistics, compatibility JSON if needed, and nextpnr evidence with success or exact failure.

- [ ] **Step 1: Specify evidence-preservation tests**

Assert exact target/chipdb, `synth_xilinx -family xc7`, compressed logs, GNU time output, mapped stats, exit status, timing evidence, hashes, and source manifest. Assert the derivation does not hard-code an expected failure and does not require `--ignore-initial` without emitting an initialization audit.

- [ ] **Step 2: Run and confirm the missing-baseline failure**

Run: `python -m pytest tests/test_rc_serving_w4a8_nix.py -q`

Expected: FAIL because `nix/rc-w4a8-synthesis-baseline.nix` is absent.

- [ ] **Step 3: Implement success-or-failure evidence derivations**

Generalize the proven W8A8 baseline structure. Capture Yosys/nextpnr exit codes rather than making the evidence derivation disappear on tool failure. Parse LUT, FF, BRAM18/36, DSP48E1, carry, clock constraint, legal Fmax, critical paths, failure stage, wall time, and peak RSS. Audit `initial`/`$readmem*` use and record whether synthesis preserved it.

- [ ] **Step 4: Build all stages and validate receipts**

Run the unit tests and each Nix stage with `--no-link --print-out-paths -L`. Expected: mapped utilization is present. If P&R succeeds, the receipt contains legal timing and critical paths; if it fails, it contains the exact capacity/tool failure and explicitly marks timing unavailable.

- [ ] **Step 5: Commit synthesis baseline wiring**

```bash
git add nix/rc-w4a8-synthesis-baseline.nix tests/test_rc_serving_w4a8_nix.py flake.nix
git commit -m "build: add RC W4A8 synthesis baseline"
```

### Task 8: Publish the compiler-oracle result and freeze the next interface

**Files:**
- Create: `docs/results/2026-08-12-rc-w4a8-compiler-oracle.md`
- Modify: `docs/glossary.md`

**Interfaces:**
- Consumes: actual Nix output paths and all functional/synthesis receipts.
- Produces: a durable baseline report and the exact oracle inputs required by the later manual-RTL plan.

- [ ] **Step 1: Create a report checklist from receipts**

The report must include model/tensor/SV hashes; quantization rules; every simulation suite and context count; Yosys and nextpnr resource tables; timing/critical paths or their justified absence; runtimes/RSS; initialization audit; Nix reproduction commands; and exact failures.

- [ ] **Step 2: Verify every reported number against its source**

Run a small Python or `jq` comparison command for each JSON-derived table and `nix path-info` for each store path. Expected: no manually transcribed value differs from its receipt.

- [ ] **Step 3: Write the measured report without extrapolated claims**

State separately whether (a) PyTorch-to-RTL passes, (b) the finite domain is exhaustive, (c) mapped synthesis succeeds, (d) P&R succeeds, and (e) initialized learned weights are synthesis-visible. Define “W4A8 compiler oracle” in the glossary as the immutable transaction-level reference, not the final accelerator.

- [ ] **Step 4: Run final verification**

Run:

```bash
python -m pytest tests/test_rc_serving_w4a8_contract.py tests/test_rc_serving_w4a8_export.py tests/test_rc_serving_w4a8_equivalence.py tests/test_rc_serving_w4a8_nix.py -q
git diff --check
git status --short
```

Expected: all tests PASS; only the intended report/glossary changes and the preserved unrelated user files are visible.

- [ ] **Step 5: Commit the baseline report**

```bash
git add docs/results/2026-08-12-rc-w4a8-compiler-oracle.md docs/glossary.md
git commit -m "docs: record RC W4A8 compiler oracle"
```

## Follow-on boundary

Do not start the manual RTL refinement in this plan. Once Task 8 supplies the
actual packed tensor format, generated RTL interface, arithmetic behavior,
cycle bounds, and synthesis baseline, write a second design-derived plan for
the transaction wrapper, sequential GEMV, initialized BRAM, local EQY/SBY
proofs, complete sequencer, and fitting P&R milestone.
