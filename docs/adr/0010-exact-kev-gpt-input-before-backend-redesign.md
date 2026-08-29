---
status: accepted
---

# Run the exact kev-gpt model through the current pipeline before redesigning it

LLM2FPGA will first authenticate an executable PyTorch representation of the
exact TinyStories-1M package and integer semantics used by the proven
kev-gpt-derived accelerator, then run it through the existing Torch-MLIR and
CIRCT/Calyx pipeline without backend substitutions. The previous compiler
artifact came from a Hugging Face floating-point input and therefore could not
localize failures against the fixed-point accelerator. Custom RTL primitives,
streaming architecture, or a separate autoregressive runtime may be introduced
only in response to the first reproducible frontier from the exact-input run.
