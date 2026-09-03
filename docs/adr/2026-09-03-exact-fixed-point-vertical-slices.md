# Exact fixed-point vertical slices

## Decision

Salvage the TinyStories compiler through exact-model-derived vertical slices.
Use project-owned out-of-tree contract passes and an `llm2fpga.fixed` schema
above Calyx. Start with the exact-shape `GEMV -> requantization` crossing,
using captured frozen-prompt tensors. Keep values logical SSA until a separate
storage/control lowering assigns memories. Require bit-exact checkpoint hashes
and a matching generated-Calyx trace before expanding the slice.

## Consequences

PyTorch remains the semantic authority; kev-gpt is an architectural and
performance reference only. Calyx provides explicit control/memory/SV lowering
but is not the fixed-point dataflow IR. Micro-fixtures may speed bring-up only
when paired with the exact contract slice.
