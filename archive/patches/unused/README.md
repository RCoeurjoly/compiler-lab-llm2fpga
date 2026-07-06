# Unused Patch Archive

This directory contains local patch stacks kept only as historical reference.
They are not applied by the flake, `torch-mlir.nix`, or any active package.

Do not treat these patches as part of the compiler pipeline contract. Reviving
one requires a new design note explaining why upstream PyTorch quantization,
torch-mlir, MLIR/CIRCT passes, or official Calyx cannot express the required
behavior.
