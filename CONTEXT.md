# LLM2FPGA Verification Context

This context defines the terms used to establish trustworthy correspondence between the quantized PyTorch model and generated FPGA RTL.

## Verification

**Equivalence gate**:
A finite, reproducible test that accepts the generated implementation only when it exactly matches the frozen PyTorch reference for every required output in the agreed query set.
_Avoid_: similarity check, spot check, approximate validation

**Frozen reference**:
The immutable PT2E W8A8 model state, calibration-derived graph, inputs, expected six logits, and expected token IDs used as the numerical oracle.
_Avoid_: current PyTorch model, live reference

**Representative core**:
A deliberately small TinyStories model instance used as the working unit for end-to-end compiler, simulation, and hardware experiments, subject to its own stated predictive-validity evidence.
_Avoid_: toy model, handwritten model

**Smoke gate**:
The one-query form of the equivalence gate used for rapid diagnosis and iteration.
_Avoid_: informal test, partial equivalence

**Full gate**:
The four-query form of the equivalence gate required before claiming RC equivalence.
_Avoid_: benchmark run, exhaustive proof

**Baseline profile**:
A measurement of the unmodified Nix-managed equivalence path that separates artifact generation, compilation, simulator execution, schedule progress, and output comparison costs.
_Avoid_: wall-clock estimate, build impression

**Cost attribution**:
Evidence that assigns time, memory, or execution-rate cost to a specific generated SV, Verilator, C++, simulator, or schedule component.
_Avoid_: optimization guess, generic profiling

**Observable result**:
The six raw signed int8 logits and the lowest-index argmax token ID sampled after the SV completion contract is satisfied.
_Avoid_: approximate logits, formatted output
