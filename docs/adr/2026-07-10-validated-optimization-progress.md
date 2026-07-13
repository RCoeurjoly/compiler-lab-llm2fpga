# ADR: Measure progress as validated optimization claims

- Status: accepted
- Date: 2026-07-10

## Context

Task 3 demonstrated substantial FPGA resource overuse. Task 6 is evaluating
multiple reduction strategies, including handshake removal, TOSA lowering,
DDR3 memory externalization, and quantization. These strategies have not yet
been integrated into one working system, and the previous Task 3 workflow did
not establish PyTorch-to-SystemVerilog functional equivalence.

Reducing model hyperparameters into a representative core improves iteration
speed by only about 4x. That makes RC useful as one test target, but
insufficient as the project-wide abstraction: it can hide costs and failures
that arise from model structure, lowering strategy, interfaces, or numeric
representation.

## Decision

Define project progress as validated optimization claims. Every claim should
report three dimensions:

1. Semantic confidence: functional equivalence or a documented numerical
   tolerance between the reference and generated implementation.
2. Resource effect: measured change in LUTs, FFs, BRAM, DSPs, and other
   relevant FPGA metrics.
3. Iteration cost: wall-clock and memory cost for the compiler/lowering and,
   when selected, the full synthesis path.

Use three coordinated test targets:

- Full model for final integration and generality.
- Representative core for an end-to-end pipeline smoke test.
- Isolated components such as attention, embedding, or memory paths for fast
  attribution of individual reduction strategies.

Each isolated component must have an explicit contract covering tensor shapes,
dtypes, memory ownership, numerical tolerance, and interface protocol before
its result is treated as evidence for the full model.

## Equivalence reference

Use the Task 2 matmul equivalence workflow in `/home/roland/LLM2FPGA` as the
initial implementation template. It computes golden outputs with the PyTorch
module, embeds the expected values into a generated SystemVerilog testbench,
runs the generated SV with Verilator, compares expected versus observed
outputs, and emits a machine-readable result. Task 6 component harnesses
should preserve this reference-data and simulator pattern while adding the
explicit tolerance and dtype metadata required for quantized experiments.

## Sequencing

Build the equivalence infrastructure before treating additional resource
reduction experiments as evidence. The first implementation should reproduce
the Task 2 matmul proof, then generalize the harness for component and
full-model test targets.

The active harness lives in this repository. The Task 2 implementation remains
the historical reference, while the current harness owns the reusable
configuration, test vectors, tolerances, simulator invocation, and result
schema used by Task 6.

## Experiment structure

Evaluate reduction strategies as staged ablations. First establish a
reproducible baseline, then enable one strategy at a time, requiring
equivalence before accepting resource measurements. Evaluate combinations only
after the individual effects are known, so interaction effects are visible
instead of being mistaken for single-strategy improvements.

## Graph-derived components

Do not define the component taxonomy by hand in advance. First inspect the
actual TinyStories Torch-MLIR/Linalg artifacts and enumerate candidate
components from their operations, SSA dependencies, shapes, dtypes, constants,
and possible cut points. A candidate becomes a test component only after its
inputs, outputs, weight ownership, and reference tensors can be identified.

Torch-MLIR is the canonical semantic discovery boundary because it is the
project's PyTorch-to-MLIR entry point. Component identity should be defined
there first and remain independent of any particular downstream dialect such
as Linalg. Downstream extractors may project a discovered component into
Linalg, TOSA, SCF, Calyx, or another representation when a strategy requires
that view.

## Component-cut boundary

Use the exported PyTorch FX/ATen graph as the authoritative component-cut
boundary. It is explicit about tensor dependencies and remains executable for
reference evaluation, while being the graph that is subsequently passed toward
Torch-MLIR. Torch-MLIR validates lowering of each selected cut; downstream
dialect projections are strategy-specific.

Every selected FX/ATen region must be a standalone executable component with
explicit tensor inputs and outputs, explicit or separately supplied
parameters, no hidden dependence on unrelated graph state, a callable PyTorch
reference wrapper, a corresponding Torch-MLIR input, and a manifest containing
shapes, dtypes, layout, parameter hashes, and tolerance.

Initial extraction uses contiguous topological regions of the exported graph,
preserving execution order and requiring clear tensor boundaries. Arbitrary
node subsets are deferred until the simpler region model has been validated.

Implement extraction with standard `torch.fx` graph/module utilities and
retain the exported graph's node metadata. Custom code is limited to component
manifests, parameter capture, reference wrappers, and validation; no second
general-purpose graph representation is introduced.

The inspector emits three artifacts: a canonical `graph-inventory.json` with
operations, metadata, dependencies, shapes, dtypes, constants, parameter
references, and graph hashes; a human-readable summary with operation counts,
hotspots, and FTS-versus-RC differences; and candidate-region records with
explicit interfaces and extraction rationale. Inspection does not mutate the
model or run lowering.

Graph identity is composite: canonical exported FX/ATen graph hash,
model/checkpoint hash, adapter/source hash, export configuration and
example-input signature, PyTorch and Torch-MLIR/toolchain versions, dtype and
quantization configuration, and graph-inventory schema version.

## Baseline hierarchy

- Primary baseline: the existing full TinyStories FP32 Task 3 flow, including
  its pinned toolchain and resource-report methodology.
- Fast development baseline: RC with the same semantic and lowering
configuration wherever possible.
- Component baseline: the corresponding unoptimized FP32 component with the
  same shapes, weights, interface, and test vectors.

Run graph inspection on full TinyStories first and on RC second using the same
inspector. Compare the inventories before selecting components, so RC-specific
shortcuts are not mistaken for general TinyStories structure.

RC is a development target, not evidence that an optimization generalizes to
FTS. Every result records the baseline identity and relevant artifact hashes.

## Claim records

Each experiment emits one machine-readable claim record containing the baseline
and variant identities, strategy set, model/component contract, input/weight
or calibration hashes, equivalence status and tolerance, compiler timings and
peak memory, artifact hashes and sizes, optional FPGA resource metrics,
toolchain/environment identity, and a status such as `pass`,
`fail-equivalence`, `fail-lowering`, or `incomplete`. Generated summary tables
are views over these records rather than the source of truth.

## Validation cadence

Exploratory iterations stop at RTLIL and run structural checks, diagnostics,
and lightweight artifact statistics. An evidence checkpoint additionally emits
SV and runs the Task 2-style PyTorch-to-SV equivalence test before any
optimization claim or resource result is recorded. Full synthesis remains a
separate selected checkpoint.

## Consequences

No resource reduction is considered successful solely because it compiles or
because a smaller model uses fewer resources. The project will need a
comparison matrix and reusable equivalence harnesses. RC remains valuable for
pipeline development, while full-model runs remain necessary to establish
generality.
