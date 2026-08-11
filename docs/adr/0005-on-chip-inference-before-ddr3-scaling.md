# Demonstrate fully on-chip inference before DDR3 scaling

Status: accepted

The first complete RC inference milestone keeps the frozen model weights and
all token-loop state in FPGA on-chip memory. It must demonstrate bit-exact
multi-token inference in simulation, then pass mapped synthesis and constrained
place-and-route on the XC7K480T without a DDR3 controller or DDR3 traffic in the
token loop. Weight initialization may be compiled into inferred BRAMs. Resource
evidence must distinguish weights, activations, scratch storage, and context or
KV state; simulation success alone is not a claim that the design fits the
device.

This sequencing isolates compute, control, quantization, and local-memory
behavior from DDR3 protocol and board-integration risk. It also establishes the
smallest useful autonomous inference system and a measured on-chip capacity
boundary. If the current W8A8 RC does not fit, the experiment may reduce model
dimensions or weight precision, but it must retain the complete token-generation
loop and record the exact model and memory image used.

DDR3 is introduced only as a subsequent scaling stage, after the fully on-chip
checkpoint and its fit or failure boundary have been recorded. That stage may
externalize weights and, when required, context or KV state through a bounded
memory service, and must repeat functional-equivalence, synthesis, P&R, and
performance gates. DDR3 results do not replace or retroactively qualify the
on-chip baseline. This decision supersedes ADR-0002's DDR3-first sequencing;
ADR-0002 remains as the historical rationale for the rejected order.
