# Full TinyStories W8A8 TOSA–Handshake Scout Design

## Objective

Connect the full TinyStories PT2E W8A8 model to the proven Handshake hardware
backend through TOSA, generate real SystemVerilog if the compiler permits it,
and collect Yosys resource statistics. This scout deliberately avoids Calyx.

## Pipeline

The experiment uses this route:

```text
Full TinyStories PT2E W8A8 ExportedProgram
-> Torch-MLIR
-> TOSA
-> PT2E zero-point legalization
-> TOSA validation
-> Linalg
-> CF
-> Handshake
-> HW
-> SV
-> Yosys statistics
```

This differs from the Task 3 baseline only at the frontend. Task 3 lowered
Torch directly to Linalg; this scout inserts the TOSA boundary and its checked
legalization before rejoining the existing Linalg-to-Handshake hardware path.

## Repository Integration

Add a public `tinystories-w8a8-via-tosa` alias backed by the existing TOSA
Handshake pipeline. Its stages must come from the existing registered
`tinystories-w8a8` model and existing pipeline constructors; do not duplicate
the lowering implementation or introduce a Calyx dependency.

The alias must expose the normal Handshake pipeline stages through
`yosys-stat`. Tests must establish that its frontend is TOSA, its backend is
Handshake-to-SV, and its stage list does not contain Calyx.

## Execution and Evidence

Run the complete `tinystories-w8a8-via-tosa-yosys-stat` target under the
existing build monitor. Preserve:

- exit status and first failing stage or operation;
- monitored wall time and sampled peak memory;
- compiler artifact sizes for stages reached;
- genuine generated SV and Yosys statistics, if reached;
- remaining float-operation evidence and external floating-point primitives.

Do not accept placeholder SV or infer resource usage from an earlier stage.
If the run fails, the first new compiler frontier is the result and later
stages are explicitly recorded as not reached.

## Interpretation

PT2E W8A8 remains QDQ-heavy and leaves floating-point computation in the
current graph. Reaching SV does not by itself establish integer-only hardware.
Resource results must therefore state whether floating-point operations were
lowered to external primitives and must not attribute all resource changes to
integer quantization.

This is a provisional compiler and resource scout. Functional equivalence,
model-quality validation, board validation, representative calibration, and
SmoothQuant remain out of scope.

## Success Criteria

The integration is complete when:

1. The public alias selects TOSA plus the Handshake backend and excludes Calyx.
2. Repository regression tests and Nix flake evaluation pass.
3. The full monitored target is attempted to its genuine terminal frontier.
4. A machine-readable result and concise report record the observed outcome.
5. If SV and Yosys are reached, the report includes actual synthesis
   statistics; otherwise it clearly records why they were not reached.
