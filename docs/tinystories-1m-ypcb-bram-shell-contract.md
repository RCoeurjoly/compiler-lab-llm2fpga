# TinyStories-1M BRAM-only YPCB shell contract

The proven kev-gpt YPCB tops establish the board-facing contract for the
compiler path. The physical top has `SYS_CLK`, active-low `SYS_RSTN`, and a
three-bit LED status output. The interactive top connects the BSCAN packet
endpoint to `tinystories_packet_controller`, which drives the sequencer with:

- 16-bit prompt tokens and token IDs;
- `prompt_valid`/`prompt_ready` input handshake;
- `start`, `requested_tokens`, `token_valid`, and `token_ready` execution
  handshake;
- `busy`, `error`, and 8-bit `error_code` status;
- debug status plus embedding/layernorm observability.

For this milestone the compiler-generated core must implement the sequencer
side of this contract and store all weights/activations in FPGA BRAM. The
board shell remains hand-written and stable, following
`tinystories_interactive_top.sv` and `tinystories_selftest_top.sv` from
kev-gpt. PCIe, DDR3, and transport redesign are outside this shell milestone.

## Current compiler gap

The existing compiler comparison RTL exposes a tensor-level
`llm2fpga_transformer_block_tensor` interface (`start`, `position`, wide
Q16/weight buses, `done`, and `output_q16`); it does not yet expose the
kev-gpt token sequencer handshake. The first top-module task is therefore an
explicit adapter/core boundary, not a direct wire-up: either the compiler
emits the token-level interface, or a deterministic BRAM-backed adapter
translates the shell protocol into the tensor-block interface.
