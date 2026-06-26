# llm2fpga-mlir-bringup

Compiler bring-up lab for the latest working Task 3-derived pipeline currently
embedded in `~/LLM2FPGA` branch `task6-crisp`.

The first flake cut keeps the reusable MLIR/CIRCT/Yosys pipeline and exposes a
small TinyStories model registry:

- `tinystories-fp32`: full TinyStories-1M FP32 export.
- `tinystories-representative-core-fp32`: reduced FP32 TinyStories core.
- `tinystories-representative-core-w4a8`: reduced PT2E static W4A8 TinyStories
  core using `TINYSTORIES_PYTORCHAO_WEIGHT_BITS=4` and
  `TINYSTORIES_PYTORCHAO_ACTIVATION_BITS=8`.

Each registry entry expands into stage packages such as:

```sh
nix build .#tinystories-representative-core-w4a8-hf-snapshot
nix build .#tinystories-representative-core-w4a8-pytorch-exported
nix build .#tinystories-representative-core-w4a8-torch
nix build .#tinystories-representative-core-w4a8-linalg
```

The `*-pytorch-exported` package contains the serialized `ExportedProgram`
consumed by the `*-torch` package, so torch-mlir no longer rebuilds the PyTorch
export inline.

The current path is intentionally the Task 3-derived path, including Handshake.
No-handshake and TOSA branches should be added as separate pipeline variants
after this baseline is verified.
