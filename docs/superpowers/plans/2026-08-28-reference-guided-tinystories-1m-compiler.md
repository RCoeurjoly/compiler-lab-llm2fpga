# Reference-guided TinyStories-1M compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing compiler pipeline reproduce the validated kev-gpt TinyStories-1M implementation, beginning with a contract-aligned one-block token-step comparison and ending with exact FPGA inference.

**Architecture:** Treat kev-gpt as a behavioral and high-level architectural reference, never as source to copy. Analyze the existing compiler-generated 1M RTL first, align its model/quantization/memory contract, extract one complete transformer-block token step, and use provenance-linked resource/timing evidence to select one compiler change before attempting full-model hardware validation.

**Tech Stack:** Nix flake, pinned PyTorch/Torch-MLIR/CIRCT, SystemVerilog, Yosys, nextpnr-xilinx/OpenXC7, existing YPCB programming and inference tools, Python 3.11 inside the Nix environment.

**Spec:** `docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`

## Global Constraints

- The active compiler backend targets TinyStories-1M first; later family targets are 3M, 8M, 28M, and 33M.
- TinyStories-1Layer-21M and arbitrary PyTorch models are out of scope for this phase.
- The Representative Core is historical research only, not a milestone or acceptance gate.
- DDR3 integration, UberDDR3 reliability work, and PCIe transport changes are deferred.
- The kev-gpt source is not copied into compiler output or submitted RTL.
- Existing LLM-assisted history is preserved and disclosed; new substantive assistance is provenance-tracked.
- Do not program hardware with an artifact that has not passed timing and provenance checks.
- Use the fixed frozen model/package, tokenizer, quantization, prompt, and 16-token reference throughout the 1M gate.
- FPGA acceptance requires three matching cold-start runs; timing/resource/latency/throughput are reported separately.

---

### Task 1: Inventory and freeze the TinyStories-1M reference contract

**Files:**
- Create: `artifacts/reference/tinystories-1m-kev-gpt-contract.json`
- Create: `docs/results/2026-08-28-tinystories-1m-reference-contract.md`
- Inspect: `docs/project-plan_v2.org`, `artifacts/`, and the pinned kev-gpt package manifest
- Test: `tests/test_tinystories_1m_reference_contract.py`

**Interfaces:**
- Consumes: the validated kev-gpt model package, tokenizer, prompt fixture, and existing hardware/reference logs.
- Produces: a schema-validated JSON contract with model/tokenizer/package hashes, quantization, memory image hash, command ABI, prompt IDs, expected 16 tokens, and baseline measurements.

- [ ] **Step 1: Write the failing contract-schema test**

```python
def test_contract_contains_frozen_1m_identity():
    contract = load_contract()
    assert contract["model"]["name"] == "TinyStories-1M"
    assert contract["model"]["n_layer"] == 8
    assert contract["model"]["hidden_size"] == 64
    assert len(contract["reference"]["tokens"]) == 16
```

- [ ] **Step 2: Run the test and verify it fails because the contract file is absent**

Run: `nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_reference_contract.py' -v`.

Expected: FAIL with a missing contract/artifact error.

- [ ] **Step 3: Populate the contract from hashes and existing evidence**

Record the exact kev-gpt package manifest hash, tokenizer hash, model image hash, quantization/scales, command ABI, prompt token IDs, expected tokens, and baseline timing/resource metadata. Do not infer missing values; mark the contract incomplete and stop if an identity cannot be verified.

- [ ] **Step 4: Implement strict contract loading**

Add `load_contract()` to the test helper. It must reject missing fields, wrong model identity, wrong layer/hidden/head dimensions, non-16-token references, and malformed hashes.

- [ ] **Step 5: Run the focused test**

Run: `nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_reference_contract.py' -v`

Expected: PASS with the frozen contract loaded from the repository artifact.

- [ ] **Step 6: Commit the contract**

```bash
git add artifacts/reference/tinystories-1m-kev-gpt-contract.json docs/results/2026-08-28-tinystories-1m-reference-contract.md tests/test_tinystories_1m_reference_contract.py
git commit -m "docs: freeze TinyStories-1M reference contract"
```

### Task 2: Locate and extract the existing compiler 1M RTL slice

**Files:**
- Create: `artifacts/comparison/tinystories-1m-slice-manifest.json`
- Create: `scripts/comparison/extract_tinystories_1m_block_slice.py`
- Create: `tests/test_tinystories_1m_slice_manifest.py`
- Inspect: existing TinyStories MLIR/SV/RTLIL artifacts and Nix derivations referenced by `flake.nix`

**Interfaces:**
- Consumes: the frozen contract from Task 1 and the existing compiler-generated TinyStories-1M RTL artifact.
- Produces: a manifest identifying the one complete transformer-block token-step slice, its source locations, dependency closure, and artifact hashes.

- [ ] **Step 1: Write the failing manifest test**

```python
def test_slice_manifest_names_one_complete_block():
    manifest = load_slice_manifest()
    assert manifest["model"] == "TinyStories-1M"
    assert manifest["slice"]["kind"] == "one_transformer_block_token_step"
    assert manifest["slice"]["dependency_closure"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_slice_manifest.py' -v`

Expected: FAIL because no extracted-slice manifest exists.

- [ ] **Step 3: Implement deterministic artifact discovery and extraction**

The script must accept explicit input paths, identify the block/token-step boundary from module names or provenance annotations, copy only the required source/IR artifacts, compute SHA-256 hashes, and fail closed if the closure includes an unbounded full-model dependency.

- [ ] **Step 4: Add contract identity checks**

Require the source artifact’s model/package metadata to match Task 1 before writing the manifest. A mismatch must produce `contract_mismatch`, not a comparison artifact.

- [ ] **Step 5: Run focused tests**

Run: `nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_slice_manifest.py' -v`

Expected: PASS and a manifest with stable hashes and explicit source provenance.

- [ ] **Step 6: Commit the slice manifest**

```bash
git add scripts/comparison/extract_tinystories_1m_block_slice.py tests/test_tinystories_1m_slice_manifest.py artifacts/comparison/tinystories-1m-slice-manifest.json
git commit -m "feat: identify TinyStories-1M comparison slice"
```

### Task 3: Build the kev-gpt/reference and compiler slice comparison harness

**Files:**
- Create: `scripts/comparison/compare_tinystories_1m_slice.py`
- Create: `tests/test_tinystories_1m_slice_comparison.py`
- Create: `artifacts/comparison/tinystories-1m-slice-comparison.json`
- Create: `docs/results/2026-08-28-tinystories-1m-slice-comparison.md`

**Interfaces:**
- Consumes: Task 1 contract, Task 2 slice manifest, reference traces, compiler RTL simulation traces, Yosys statistics, and nextpnr timing reports.
- Produces: a machine-readable comparison and a report containing equivalence status, resource/timing deltas, and provenance-linked waste candidates.

- [ ] **Step 1: Write failing tests for contract mismatch and successful comparison**

```python
def test_comparison_rejects_mismatched_quantization():
    result = compare(reference, compiler, quantization="different")
    assert result["status"] == "contract_mismatch"

def test_comparison_reports_resource_and_timing_fields():
    result = compare(reference_fixture, compiler_fixture)
    assert result["status"] == "aligned"
    assert "lut_delta" in result["resources"]
    assert "critical_paths" in result["timing"]
```

- [ ] **Step 2: Run tests to verify the comparison harness is absent**

Run: `nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_slice_comparison.py' -v`

Expected: FAIL with missing comparison function/artifact errors.

- [ ] **Step 3: Implement comparison inputs and status model**

Implement explicit statuses `contract_mismatch`, `functional_mismatch`, `aligned`, and `incomplete`. Require exact checkpoint tensors and final token outputs before calculating efficiency deltas.

- [ ] **Step 4: Add resource/timing parsers**

Parse Yosys LUT/FF/BRAM/DSP/memory statistics and nextpnr maximum frequencies, worst paths, cycles/token, and interface overhead. Preserve raw report hashes and paths in the JSON output.

- [ ] **Step 5: Add provenance-linked waste-map generation**

For each excess buffer, operator, mux, or reduction, record the compiler stage/module and source operation from RTL annotations. Never label an item as waste without a measured delta.

- [ ] **Step 6: Run focused tests and the real comparison**

Run: `nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_slice_comparison.py' -v`

Then run the Nix-managed simulation and synthesis/report commands for the extracted slice. Expected result: either a precise contract/functional mismatch or an aligned comparison with a ranked waste map.

- [ ] **Step 7: Commit the comparison harness and report**

```bash
git add scripts/comparison/compare_tinystories_1m_slice.py tests/test_tinystories_1m_slice_comparison.py artifacts/comparison/tinystories-1m-slice-comparison.json docs/results/2026-08-28-tinystories-1m-slice-comparison.md
git commit -m "feat: compare compiler RTL with TinyStories-1M reference"
```

### Task 4: Apply one evidence-backed compiler optimization

**Files:**
- Modify: the specific compiler lowering/scheduling/template file named by the Task 3 waste map
- Create: `tests/test_tinystories_1m_optimization_regression.py`
- Create: `artifacts/comparison/tinystories-1m-optimization-result.json`
- Update: `docs/results/2026-08-28-tinystories-1m-slice-comparison.md`

**Interfaces:**
- Consumes: one ranked waste candidate from Task 3.
- Produces: one isolated compiler change with before/after functional, resource, and timing evidence.

- [ ] **Step 1: Write a regression test for the selected waste candidate**

The test must exercise the exact slice and assert the frozen checkpoint/output plus the expected structural property (for example, one buffer instead of two or a pipelined reduction boundary).

- [ ] **Step 2: Run the regression test before changing code**

Run the focused Nix/Python test command recorded in the comparison report. Expected: PASS for current behavior and a baseline structural count.

- [ ] **Step 3: Implement only the selected change**

Do not modify PCIe, DDR3, tokenizer, model weights, or unrelated lowering stages. Keep the change independently attributable to the waste-map entry.

- [ ] **Step 4: Re-run simulation and structural checks**

Run the focused regression, Yosys elaboration, and slice simulation. Expected: exact functional match and no new unresolved modules or blackboxes.

- [ ] **Step 5: Re-run resource/timing measurement**

Use the same Nix derivations, constraints, and tool versions as Task 3. Accept the optimization only if it preserves functional equivalence and improves the targeted measured cost without regressing required timing.

- [ ] **Step 6: Commit the isolated optimization**

```bash
git add tests/test_tinystories_1m_optimization_regression.py artifacts/comparison/tinystories-1m-optimization-result.json docs/results/2026-08-28-tinystories-1m-slice-comparison.md
git commit -m "opt: reduce measured TinyStories-1M compiler overhead"
```

Also stage the exact lowering/scheduling/template source path recorded by the
Task 3 comparison manifest before committing.

### Task 5: Integrate the validated compiler path into full TinyStories-1M

**Files:**
- Modify: existing TinyStories-1M compiler pipeline configuration and RTL integration files identified by Tasks 2–4
- Create: `artifacts/tinystories-1m/compiler-build-manifest.json`
- Create: `docs/results/2026-08-28-tinystories-1m-compiler-build.md`
- Test: existing Nix simulation, Yosys, and nextpnr targets for the 1M path

**Interfaces:**
- Consumes: the aligned and optimized one-block slice.
- Produces: complete compiler-generated TinyStories-1M RTL, synthesis reports, timing-closed bitstream candidate, and provenance manifest.

- [ ] **Step 1: Add a full-model contract gate**

Before building, verify that the generated package, tokenizer, quantization, memory image, and command ABI equal Task 1. Abort on mismatch.

- [ ] **Step 2: Run full-model simulation**

Run the deterministic 16-token frozen prompt through the compiler-generated RTL and compare every available checkpoint plus final tokens against the reference. Expected: exact match before hardware work.

- [ ] **Step 3: Run Yosys and constrained nextpnr-xilinx**

Use the fixed target board, constraints, clock requirements, and reproducible tool closure. Record LUT/FF/BRAM/DSP, Fmax, worst paths, seed, and all source hashes.

- [ ] **Step 4: Reject non-fitting artifacts**

Do not program or publish a bitstream candidate unless required clocks close and the provenance manifest verifies.

- [ ] **Step 5: Commit the full compiler build manifest and report**

```bash
git add artifacts/tinystories-1m/compiler-build-manifest.json docs/results/2026-08-28-tinystories-1m-compiler-build.md
git commit -m "build: close compiler-generated TinyStories-1M path"
```

### Task 6: Perform the three-run TinyStories-1M FPGA gate

**Files:**
- Create: `artifacts/hardware/tinystories-1m-compiler-cold-runs.json`
- Create: `docs/results/2026-08-28-tinystories-1m-compiler-hardware.md`
- Use: existing YPCB programming and inference scripts; do not alter transport or DDR3 configuration

**Interfaces:**
- Consumes: Task 5 timing-closed bitstream and verified package manifest.
- Produces: three cold-start hardware logs, exact-token comparison, latency, and final acceptance status.

- [ ] **Step 1: Verify board and artifact identity**

Check the bitstream SHA-256 and board target against the manifest. Do not proceed with a stale or unverified image.

- [ ] **Step 2: Program and run the frozen prompt once**

Capture token output, cycle count, wall-clock latency, status, and any available trace hash. Expected: exact 16-token match within 300 seconds.

- [ ] **Step 3: Repeat two cold starts**

Power-cycle/reinitialize according to the documented board protocol and repeat without changing inputs or artifacts. Expected: all three outputs and required hashes match.

- [ ] **Step 4: Write the acceptance report**

Mark success only when all three runs match exactly and timing/provenance gates are green. Otherwise classify the first failing gate and retain all logs.

- [ ] **Step 5: Commit the hardware evidence**

```bash
git add artifacts/hardware/tinystories-1m-compiler-cold-runs.json docs/results/2026-08-28-tinystories-1m-compiler-hardware.md
git commit -m "test: validate compiler-generated TinyStories-1M on FPGA"
```

### Task 7: Extend the backend to the remaining TinyStories family

**Files:**
- Modify: TinyStories-specific model import/configuration and RTL-generation templates
- Create: `artifacts/scaling/tinystories-family-results.json`
- Create: `docs/results/2026-08-28-tinystories-family-scaling.md`
- Test: per-model contract, simulation, synthesis, and hardware gates as capacity allows

**Interfaces:**
- Consumes: the validated 1M backend and contract format.
- Produces: reproducible 3M/8M/28M/33M scaling matrix; each model is classified as fitting, non-fitting, or blocked with evidence.

- [ ] **Step 1: Add model-config contract tests**

Require each model manifest to identify checkpoint, tokenizer, dimensions, quantization, memory estimate, and expected acceptance mode.

- [ ] **Step 2: Generate and simulate each model**

Run the same TinyStories-specific lowering and exact reference comparison. Record failures at contract, simulation, synthesis, timing, or hardware gates.

- [ ] **Step 3: Generate resource/timing matrix**

Fit only descriptive scaling trends to measured results; do not extrapolate an unmeasured hardware success claim.

- [ ] **Step 4: Commit the scaling report**

```bash
git add artifacts/scaling/tinystories-family-results.json docs/results/2026-08-28-tinystories-family-scaling.md
git commit -m "docs: characterize TinyStories compiler scaling"
```
