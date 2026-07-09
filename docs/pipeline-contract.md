# Pipeline Contract

This repo is a compiler-pipeline lab. Active deliverables should be explainable
as a sequence of model construction, PyTorch quantization, compiler IR emission,
MLIR/CIRCT passes, optional official Calyx lowering, and hardware/backend
inspection.

## Allowed transformations

- PyTorch model construction from checked-in adapter code and pinned model
  snapshots.
- PyTorch quantization, including PT2E and torchao flows, when the transformation
  can be compared against the unquantized model and downstream simulation.
- Named model simplifications that are documented in adapter code as model
  simplification rather than hidden compiler workarounds.
- torch-mlir frontend lowering from a serialized PyTorch ExportedProgram.
- MLIR/CIRCT passes invoked through checked-in pipeline scripts or Nix
  derivations.
- Official Calyx lowering stages, exposed with names that make the backend clear.
- Diagnostics that report blockers, provenance, or quality metrics without
  changing compiler IR.

## Disallowed transformations

- Handwritten textual MLIR rewrites in pipeline stages.
- Local patch stacks silently applied to torch-mlir, CIRCT, or other compiler
  dependencies.
- Model edits mixed into quantization or export cleanup without a named phase.
- Derivation aliases whose names hide the model, frontend, or backend path.
- Diagnostics scripts that mutate the active compiler pipeline.

## Active pipeline variants

- `baseline`: PyTorch ExportedProgram -> torch-mlir -> linalg -> cf ->
  handshake -> hw -> sv.
- `via-tosa`: PyTorch ExportedProgram -> torch-mlir TOSA -> linalg -> cf ->
  handshake -> hw -> sv.
- `via-tosa-no-handshake-calyx-native-sv`: PyTorch ExportedProgram ->
  torch-mlir TOSA -> linalg -> scf -> flat-scf -> Calyx dialect ->
  `circt-translate --export-calyx` -> native Calyx -> SV. This is the current
  working Calyx SV route.
- `via-tosa-no-handshake-calyx-hw-sv`: PyTorch ExportedProgram -> torch-mlir
  TOSA -> linalg -> scf -> flat-scf -> Calyx dialect -> `--lower-calyx-to-hw`
  -> HW/SV. This is the desired direct CIRCT route and the primary failing
  target for Calyx backend debugging.
- `via-tosa-no-handshake-llvm`: PyTorch ExportedProgram -> torch-mlir TOSA ->
  linalg -> scf -> flat-scf -> llvm, used as a compiler comparison path.

Archive-only patch stacks live under `archive/patches/unused/` and are not
applied.
