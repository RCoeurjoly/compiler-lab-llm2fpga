# Read The Repo

Use this order when reading the repository for compiler-pipeline architecture.
The goal is to understand the contract first, then the package graph, then the
implementation details.

1. `docs/pipeline-contract.md`

   Start with the allowed and disallowed transformations. This is the boundary
   between model work, PyTorch quantization, MLIR/CIRCT passes, official Calyx,
   diagnostics, and archived experiments.

2. `docs/read-the-repo.md`

   Use this file as the reading index. Update it when new top-level concepts are
   added.

3. `flake.nix`

   Read the package surface and the generated pipeline aliases. The
   `active-pipeline-variants` package emits machine-readable JSON for each
   active variant, including `model`, `frontend`, `backend`, `stages`, and the
   generated package aliases.

4. `nix/models.nix`

   Read the model registry. This is where model names, adapters, snapshots,
   PyTorch export commands, and primitive inputs enter the pipeline.

5. `nix/pipeline.nix`

   Read the derivation builders and stage graph. This file defines how model
   registry entries become PyTorch export, torch-mlir, MLIR/CIRCT, Calyx, SV,
   LLVM, diagnostics, and metadata outputs.

6. `scripts/pipeline/`

   Read compiler-stage scripts here. These scripts are allowed to transform IR
   as named pipeline stages.

7. `TinyStories/model_adapter_representative_core_pt2e_static_quant.py`

   Read this adapter carefully because it has the largest pre-compiler semantic
   surface. Its phases separate representative-core model construction, model
   simplification, PT2E quantization, and export cleanup.

8. `scripts/diagnostics/`

   Read reports and blocker analysis here. Diagnostics should inspect or report;
   they should not silently become compiler stages.

9. `tests/`

   Read the tests last as executable policy. They pin the repo shape, public
   pipeline names, archived patch boundary, and compiler-pipeline assumptions.
