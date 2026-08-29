# TinyStories transformer board integration boundary

This document defines the pending board-level adapter. PCIe/JTAG transport is
unchanged; only the payload behind the existing packet controller is replaced.

## Control sequence

1. Transport receives a model/context-load command and streams complete tensor
   images into the resident weight/context memories.
2. Controller validates package and tensor hashes, then issues one token-step
   `start` pulse with `position` and prompt/context metadata.
3. `llm2fpga_transformer_block_tensor` runs to `done` without transport
   intervention.
4. Controller reads the 64-lane `output_q16` result, computes/selects the next
   token, and emits the response packet.

## Datapath boundary

The adapter must provide packed Q16.16 activations/LayerNorm parameters,
packed Q8.24 scales, signed INT8 weight images, and the causal Q/K/V history.
The verified shell currently uses these as explicit ports; production
integration should replace the wide ports with dual-port resident memories.

## Acceptance gates

The adapter is not complete until: (a) the existing transport lifecycle tests
still pass, (b) the authenticated one-block vector passes through the adapter,
(c) model-image hash/readback succeeds, and (d) the board produces the exact
16-token reference on three cold starts.

The current flake does not expose a TinyStories transformer bitstream target;
the existing FPGA target is the Calyx self-test. Adding the adapter therefore
requires a new board target and explicit source/constraint closure, rather than
just selecting a different existing package.
