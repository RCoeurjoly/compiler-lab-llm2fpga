# Pattern Diagnostics Pipeline Design

Date: 2026-06-26

## Context

The current TinyStories representative-core W4A8 pipeline can emit very large
SystemVerilog. Yosys/slang can run out of memory, and the design does not fit
the target FPGA. The current failure is too late and too large to diagnose well:
it starts from a whole representative core with vocabulary, attention, layers,
and model-level interactions.

Early analysis suggests that the quantized path may still contain dequantize /
quantize scaffolding and core float operations. The compiler laboratory needs
diagnostics that show where float leakage, DQ/Q scaffolding, growth, and tool
failures first enter the pipeline.

This design is diagnostics-first. It does not attempt to fix quantization,
remove Handshake, or add TOSA yet. Those are downstream solution paths that
should be guided by clear evidence.

## Goals

- Diagnose failures on small, auditable units before running the full
  representative core.
- Make quantization itself observable as a pipeline stage.
- Emit per-stage artifacts, reports, and adjacent-stage deltas.
- Hard-fail early on structural failures and core float leakage.
- Report growth and semantic equivalence without making them hard gates yet.
- Keep the existing TinyStories model pipeline intact while adding a separate
  pattern diagnostics subsystem.

## Non-Goals

- Do not solve W4A8 quantization quality in this first design.
- Do not introduce TOSA or a no-Handshake lowering branch yet.
- Do not make SV size or semantic mismatch hard failures in the first version.
- Do not fold pattern diagnostics into `nix/models.nix`.
- Do not hand-author W4A8 internals inside pattern models.

## Architecture

Add a separate pattern diagnostics pipeline beside the TinyStories model
pipeline.

The first-class diagnostic unit is a **pattern**, not the representative core.
Each pattern starts as a hand-authored FP32 PyTorch module. The pipeline applies
quantization and records what changed.

Initial pattern data flow:

```text
hand-authored FP32 PyTorch pattern
  -> FP32 ExportedProgram
  -> pipeline-applied quantization
  -> quantized ExportedProgram
  -> torch-mlir
  -> linalg / cf
  -> current Handshake / hw / sv baseline
  -> diagnostics ledger
```

The first implementation should include only one pattern, `linear`, and enough
infrastructure to add more patterns without changing the artifact shape.

Later patterns should be added one at a time:

- `embedding`
- `residual_add`
- `matmul`
- `layernorm`
- `gelu`
- `softmax`

TinyStories submodule diagnostics are a second tier. They should reuse the same
ledger format, but they should not block the first implementation.

## Repository Layout

Add a pattern subsystem with clear boundaries:

```text
patterns/
  linear/
    model.py
    inputs.py
    reference.py
    metadata.json

nix/patterns.nix
nix/pattern-pipeline.nix

scripts/patterns/
  materialize-pattern-exported.py
  quantize-pattern.py
  diagnose-exported.py
  diagnose-mlir.py
  diagnose-stage-delta.py
  write-diagnostics-ledger.py
```

Existing lowering scripts such as `torch_to_linalg.sh`, `linalg_to_cf.sh`, and
CIRCT/SV scripts can be reused. The existing TinyStories model registry remains
focused on full-model and representative-core artifacts.

## Pattern Contract

Each pattern directory owns only the FP32 pattern definition and deterministic
reference inputs.

- `model.py`: minimal FP32 PyTorch module.
- `inputs.py`: deterministic example inputs.
- `reference.py`: expected outputs for semantic reporting.
- `metadata.json`: pattern name, expected operation family, quantization target,
  and diagnostic rule hints.

The pattern model must not manually pack W4A8 weights or simulate int4 compute.
The pipeline is responsible for applying quantization so diagnostics can answer:

```text
Did the quantization stage transform this clean FP32 pattern into the integer
contract we expected?
```

## Package And Artifact Contract

Use a `pattern-*` package prefix to avoid collisions with TinyStories models.
For the initial `linear` pattern, expose packages such as:

```text
pattern-linear-pytorch-exported
pattern-linear-pytorch-quantized
pattern-linear-torch
pattern-linear-linalg
pattern-linear-cf
pattern-linear-handshake
pattern-linear-hw
pattern-linear-sv
pattern-linear-yosys-stat
pattern-linear-diagnostics
```

Each stage artifact should contain:

- the primary artifact, such as `exported.pt2`, `.mlir`, `sources.f`, or
  `stat.json`
- `manifest.json` with stage name, input derivation, command or tool, and
  source pattern
- cheap stage-local diagnostics where available, such as graph text, op
  histogram, dtype summary, file size, and line count

The `*-diagnostics` package is the main human entry point. Individual stage
artifacts are drill-down evidence.

Example ledger shape:

```json
{
  "pattern": "linear",
  "target": "w4a8",
  "stages": {
    "pytorch-exported": {},
    "pytorch-quantized": {},
    "torch": {}
  },
  "deltas": [
    {
      "from": "pytorch-exported",
      "to": "pytorch-quantized"
    }
  ],
  "failures": [
    {
      "stage": "torch",
      "kind": "float-leak",
      "evidence": "arith.mulf in quantized core path"
    }
  ]
}
```

## Diagnostics And Gates

Version 1 hard failures:

- missing expected file
- malformed JSON/report
- tool execution failure
- empty emitted artifact
- core float leakage in quantized-target paths

Float leakage should be checked across stages:

- FP32 exported graph
- quantized exported graph
- torch-mlir output
- linalg/cf MLIR
- later, SV metadata where useful

The first version should use a conservative denylist with simple context:

- fail on `arith.mulf`, `arith.addf`, and `math.*` in core lowered paths
- fail on float `linalg.matmul` or float matmul-like ops
- fail on `f32` constants that look like weights in quantized-target stages
- fail on dequantize/quantize scaffolding when it encloses core compute rather
  than only boundary conversion
- report generic `f32` in metadata or non-core boundary paths, but do not fail
  on it initially

The diagnostics ledger should record:

- op counts by stage
- dtype/type counts by stage
- DQ/Q/DQD counts
- known float-leak evidence
- first stage where each leak appears
- artifact sizes and line counts
- SV source file count and total bytes
- Yosys/slang status if reached
- semantic comparison status when reference vectors exist

Growth budgets and semantic equivalence are report-only in the first version.
They can become hard gates after baseline numbers exist for several patterns.

## Rollout

### Phase 1: Linear Pattern Skeleton

- Add `patterns/linear`.
- Add pattern registry/pipeline Nix files.
- Emit packages through at least:
  - `pattern-linear-pytorch-exported`
  - `pattern-linear-pytorch-quantized`
  - `pattern-linear-torch`
  - `pattern-linear-diagnostics`
- Hard-fail on structural issues and float leakage in exported/torch stages.

### Phase 2: Lowering Coverage

Extend the same pattern through the existing baseline:

- `linalg`
- `cf`
- `handshake`
- `hw`
- `sv`
- `yosys-stat`

The diagnostics ledger gains artifact sizes, op counts, SV bytes, and
Yosys/slang status.

### Phase 3: Additional Patterns

Add one pattern at a time:

- `embedding`
- `residual_add`
- `matmul`
- `layernorm`
- `gelu`
- `softmax`

Each new pattern gets a regression test and contributes to the same diagnostics
ledger format.

## Tests

Add focused tests for the pattern diagnostics contract:

- pattern packages are exposed by the flake
- each stage emits expected files
- diagnostics ledger schema is stable
- float leakage fails on a synthetic bad artifact
- clean integer-like examples do not false-positive
- no diagnostics-only script becomes orphaned

Existing model-pipeline clarity tests should remain in place.

## Future Solution Paths

The diagnostics pipeline should produce evidence for later solution work:

- better quantization application and integer lowering
- no-Handshake lowering branch
- TOSA lowering branch

Those solution paths should not be implemented until the pattern diagnostics can
show where the current pipeline first becomes float-heavy or structurally too
large.
