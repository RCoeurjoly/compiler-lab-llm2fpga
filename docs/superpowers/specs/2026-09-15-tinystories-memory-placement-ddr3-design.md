# TinyStories-1M selectable BRAM/DDR3 memory placement design

## Objective

Extend the compiler-generated TinyStories-1M path with a selectable external
memory backend while preserving the already authenticated BRAM behavior. A
single compiler artifact must be able to place immutable model weights in
on-chip BRAM or in the validated UberDDR3 interface, with the same logical
addresses, fixed-point arithmetic, token schedule, and observable results.

This is a new backend scope alongside the BRAM-only milestone. It does not
claim that the current integrated DDR3 design works; it defines the evidence
needed to make that claim.

## Frozen model contract

- Input is the exact authenticated TinyStories-1M PyTorch export used by the
  current compiler path, identified by its existing source and provenance
  hashes.
- Quantization remains W8A8: per-output INT8 weights, INT8 activations, and
  the existing Q16.16/Q8.24 fixed-point boundaries.
- MAC accumulation remains ascending signed-64-bit wrapping arithmetic.
- The frozen prompt, token checkpoints, and 16-token reference are unchanged.
- kev-gpt and handwritten RTL remain behavioral/reference oracles only.

## Placement boundary

The compiler emits a logical memory contract before technology mapping. Each
memory declaration carries a placement record with:

| Field | Meaning |
| --- | --- |
| `logical_name` | Stable compiler-owned tensor/table name |
| `space` | `bram` or `ddr3` |
| `width_bits`, `depth_words` | Logical shape before banking/packing |
| `read_only` | Whether writes are legal after initialization |
| `read_latency` | Number of cycles from request to response |
| `burst_words`, `alignment_bytes` | External-memory transfer contract |
| `address_map` | Word-to-bank/byte mapping and endianness |
| `provenance` | Source tensor hash, quantization, and placement decision |

The placement record is lowered to RTLIL attributes and consumed by an
out-of-tree Yosys pass/plugin before BRAM technology mapping. A post-placement
rewrite is explicitly out of scope because it cannot safely recover logical
memory semantics or timing intent.

## Backend architecture

Both backends implement one compiler-owned request/response protocol:

```text
read_req(valid, addr) -> read_resp(valid, data)
write_req(valid, addr, data, mask) -> write_ack(valid)
```

The BRAM backend retains the existing synchronous memory implementation. The
DDR3 backend adapts the validated two-lane UberDDR3 profile at 333/83.33 MHz;
no higher lane count or frequency is introduced. Because DDR3 has variable
latency and burst behavior, the adapter must either stall/resume the generated
controller explicitly or prefetch into a small BRAM cache while presenting the
same logical response ordering. The first implementation moves immutable
weight tables only; activations, context, accumulators, and control state stay
in BRAM.

JTAG is the initial load and diagnostic transport. PCIe is optional follow-up
work and must not be required to establish backend equivalence.

## Equivalence and acceptance gates

1. **Contract gate:** placement metadata, source hashes, tensor shapes,
   quantization, address maps, and initialization images are self-hashed and
   reproducible.
2. **Abstract-memory gate:** a cycle-accurate reference model checks ordered
   reads/writes, reset state, latency, and byte/word addressing.
3. **Standalone DDR3 gate:** the existing UberDDR3 configuration passes its
   established initialization/BIST/readback protocol without accelerator logic.
4. **Single-table gate:** one immutable projection table is lowered once to
   BRAM and once to DDR3; both produce identical read traces and output hashes
   in simulation.
5. **Full-image gate:** the complete immutable weight image loads through the
   selected transport and readback hashes exactly match the source image.
6. **Functional gate:** the generated design matches the authenticated
   one-token and then exact 16-token simulation references, with the BRAM mode
   remaining a regression.
7. **Implementation gate:** Yosys and constrained nextpnr-xilinx complete at
   the declared clocks, with resource and timing reports for both modes.
8. **Hardware gate:** each mode that reaches hardware is programmed and runs
   three cold-start YPCB trials; token outputs and runtime are recorded. No
   DDR3 success is claimed from simulation alone.

Development artifacts must complete within 30 minutes, full-model builds
within two hours, and every failure must identify the first failing gate.

## Non-goals and stop conditions

This design does not generalize to arbitrary PyTorch models, change the model
or arithmetic, add PCIe and DDR3 simultaneously, or replace compiler output
with copied kev-gpt RTL. Stop and reassess if the single-table equivalence
gate cannot pass, if the DDR3 adapter cannot preserve ordered semantics, or if
the serialized schedule is provably bandwidth-bound without a defined cache
or prefetch transformation.
