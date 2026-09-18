# Compiler DDR3 weight-bank request consolidation

## Scope and decision

Approved direction: replace the 197 separate request controllers for
`token_weight_codes_i8_b0` through `b196` with one compiler-generated shared
controller. This is an implementation experiment toward the existing
PCIe/DDR3 first-token board goal, not a replacement acceptance milestone.

This addendum governs this experiment where the older September 15 memory
placement document describes JTAG or a new transport adapter. The current
PCIe loader, physical UberDDR3 implementation, two-lane 333/83.33 MHz profile,
62.5 MHz PCIe clock, constraints, and seed 15 remain unchanged. No kev-gpt RTL
is an implementation input. Model arithmetic, schedule, prompt and image stay
authenticated and unchanged.

## Evidence motivating the experiment

The payload-reset candidate's first-token loaded-image simulation passed:
token 11 after 165,186,630 cycles and 13,116,912 requests/responses. See
`artifacts/diagnostics/2026-09-18-owner-mux-simulation/result.json` for exact
scope and hashes. Its memory model is not the physical DDR3 PHY or PCIe ingress.

The candidate's three-hour route ended with exit 124 and no routed FASM or
JSON. Its log remains at
`/tmp/compiler-ddr3-payload-reset.tywJVR/route.log`, SHA-256
`2d7ea500c9ee1a7c68563ebbd3e8260a948110f794d9e0d5776a2efe59f64c3d`.
The last reported remaining-arc count was 105,124. Placement, not final routed
timing, identified context-token bit 13 to bank 137's request register as a
critical path. This supports investigating distributed bank logic; it does
not establish the cause of routing nonconvergence or guarantee consolidation
will close timing.

The existing externalizer preserves 197 BRAM-oriented weight banks among 240
external-memory ports. Each bank has its own queue, pending state, duplicate
suppression and response state. All banks receive the same local-address mux.
Embedding reads are enabled in generated FSM state 13; LM projection reads
are enabled in state 386. The source enables are mutually exclusive. Tests
must check this source contract and reject unsupported changes; source
inspection alone is not proof of the synthesis-recoded controller.

## Architecture and compatibility boundary

Implement the optimization in the compiler-owned external-memory lowering,
currently `scripts/analysis/externalize_compiler_memory.py`, before synthesis.
Do not hand-edit an emitted model or insert reference-accelerator RTL.

Retain the existing 240-slot external-memory ABI and the pinned backend,
arbiter, command adapter and physical transport sources. Use the existing
bank-zero slot for the shared bank requester; drive the other 196 bank request
valids and addresses to zero. The 43 non-bank logical memories retain their
slots and implementations. Synthesis may remove inactive arbitration logic;
the optimization must not depend on a hand-rewritten arbiter.

Select embedding or LM bank/local-address inputs using the authenticated
mutually-exclusive enables. Generate the bank-to-byte-base lookup from the
existing manifest. Its lexical image ordering is NOT numeric bank ordering:
bank 2 does not immediately follow bank 1. Do not repack the image or compute
the base as `bank_number * bank_bytes`.

The shared controller captures bank, local address and physical byte address
as one request identity. It holds them through request backpressure and until
the response is consumed. Duplicate suppression includes bank identity, not
only local address. Reset cancels all valid/pending/completion state. It must
not emit a stale completion after reset or accept an unsolicited response.

Preserve each bank's retained read-data semantics initially: update only the
captured response owner's byte register and pulse only that bank's completion.
Keep the existing read-data muxes and completion joins. This intentionally
avoids combining request consolidation with a separate stale-data/mux
optimization. A registered response handoff may add latency; the generated
latency-tolerant schedule must absorb it without changing sampled data.

The lowering must fail closed on unexpected shapes, write enables, address
muxes, consumers, clock/reset wiring, or overlapping client-enable structure.
Invalid selectors must not create out-of-image requests or false completion.
Preserve the established invalid-selector behavior rather than silently
inventing a new token value.

## Equivalence contract and verification

Cycle counts and arbitration order among independent logical memories may
change. Compare ordered transactions per logical consumer, response values,
completion ownership, and architectural checkpoints, not a global trace hash
that assumes identical arbitration timing.

Before a full-model rebuild:

1. Test manifest address mapping for every bank and all byte offsets, including
   lexical boundaries, and reject malformed/noncontiguous bank declarations.
2. Compare the shared controller against the existing bank-controller behavior
   under the generated client protocol: stable bank/address until completion,
   and an operation boundary before reuse. Check same-local-address reads in
   different banks, repeated reads, delayed responses, arbitrary request stalls,
   reset during queued/pending/response stages, and unsolicited responses.
3. Use a small formal fixture for ownership, stable queued addresses, no lost
   or duplicate completion, and retained per-bank data. State its assumptions
   explicitly and check them separately against the full generated schedule.
4. Run the complete external-memory regressions. Verify the 240-slot ABI is
   unchanged and only one bank request controller remains in synthesized RTL.
5. Run exact-image first-token simulation through the existing production owner
   mux, including complete image write/readback. Require token 11, transaction
   diagnostics, no unmatched response and correct output backpressure. Explain
   any request-count difference before accepting it.

## Implementation and board gates

Measure synthesized resource counts, queue/decode structure and critical paths
against the payload-reset candidate. Preserve its passing simulation and the
loader-only baseline. Run a bounded placement diagnostic before another full
route; do not spend another routing window merely because a simulation passed.
Use the existing development/full-build timeboxes; no silent extensions.

A completed route and passing fixed-clock reports are necessary, but not alone
sufficient for full timing qualification: the pinned nextpnr timing model has
documented missing BRAM/DSP endpoints and estimated sequential delays. Keep
that coverage limitation explicit. Neither a timeout nor a placement-only
report qualifies a bitstream.

Only promote a provenance-verified, qualified implementation to bitstream and
board first-token testing through the established PCIe lifecycle protocol.
Record full-image readback, the authenticated first token, and hardware logs.
Do not claim full autoregressive inference or goal completion from this
consolidation experiment or its simulation.

## Stop conditions

Reject the candidate on the first evidenced semantic mismatch and localize it
before another change. If consolidation fails to reduce the intended request
structure or routing pressure, report that evidence and reassess; do not
respond with seed sweeps, weaker constraints, DDR changes or repeated longer
runs. The broader first-token board objective remains unchanged.
