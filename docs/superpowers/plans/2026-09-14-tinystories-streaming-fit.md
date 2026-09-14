# TinyStories-1M eight-row streaming fit plan

## Purpose

The exact compiler-generated 16-token design is functionally correct in
simulation but exceeds the YPCB BRAM budget. The authenticated memory plan
shows that an eight-row runtime tile is the only candidate with an ideal
logical footprint below the 955-RAMB36E1 device limit. This plan defines the
next compiler transformation; it does not change the model, arithmetic,
transport, or reference implementation.

## Transformation boundary

Add a compiler-owned `context_tile_rows` schedule parameter, fixed initially
to 8. The generated controller must iterate over all real context rows in
tiles, while retaining only state that is live across tiles:

- immutable parameter and token tables remain unchanged;
- the current tile's embedding, attention, and MLP working buffers are tile
  sized;
- prior-layer block outputs needed by later tiles are explicitly retained;
- the LM head consumes only the final real row, as in the current contract;
- tile boundaries are compiler-generated control, not host-visible protocol.

No memory is aliased unless an explicit producer/consumer lifetime proof is
recorded in the provenance receipt.

## Gates

1. Generate a four-token artifact with `context_tile_rows=8` and compare every
   existing boundary checkpoint against the authenticated oracle.
2. Generate the full 16-step artifact with the same parameter and run the
   exact two-run Verilator harness. The token sequence must remain unchanged.
3. Emit a lifetime/packing report and require its physical RAMB36 estimate to
   be at or below 955 before invoking nextpnr.
4. Run Nix/Yosys Xilinx synthesis and record RAMB36, DSP, LUT, and FF counts.
5. Only after gates 1–4 pass, build the YPCB top and attempt timing closure;
   then perform the existing three cold-start hardware acceptance.

## Failure classification

Any checkpoint mismatch is a functional frontier and must be localized at the
first tile boundary before further optimization. A correct simulation that
still exceeds 955 RAMB36E1 is a resource frontier; do not hide it with a
different transport or by substituting kev-gpt/handwritten RTL.
