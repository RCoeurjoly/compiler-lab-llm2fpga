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

## Pre-mortem and first quit point

Likely failure modes are non-deterministic fixture capture, a pattern that only
matches synthetic input, Calyx interface work obscuring arithmetic, and schema
growth before one exact checkpoint passes. The first quit point is three
bounded attempts at the captured exact `GEMV -> requantization` slice. Each
attempt must produce both bit-exact schema output and a matching
generated-Calyx trace. A result that needs model-specific escape hatches is a
failure, not an acceptance. An attempt is at most a 30-minute development
window followed by one 30-minute end-to-end build/simulation gate.
