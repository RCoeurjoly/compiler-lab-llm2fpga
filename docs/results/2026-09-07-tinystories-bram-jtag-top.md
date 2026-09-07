# TinyStories-1M BRAM/JTAG top integration checkpoint

This checkpoint replaces the autonomous timing shell with a board-facing
control boundary. The generated production `main` component now exposes:

| Signal | Direction | Meaning |
| --- | --- | --- |
| `clk`, `reset`, `start`, `valid` | input | compiler-kernel control |
| `token_index` | input | selects token slot 0 or 1 |
| `token_id` | output | selected committed token |
| `done` | output | completion of the two-token run |

`rtl/tinystories_1m_jtag_csr.sv` defines the YPCB JTAG CSR transaction:

- command `1`: write one prompt word (`command[5:4]`, `command[15:0]`);
- command `2`: reset the run state and start the kernel;
- command `3`: read status;
- command `4`: select/read token slot (`command[0]`);
- command `5`: pulse kernel reset.

The four prompt words are now driven from the CSR shadow registers into the
generated prompt-loading schedule. The board therefore loads the prompt before
the start command; no host-side token or intermediate-state feedback is used.

The production LM head now consumes each vocabulary-row GEMV result directly
from its 64-bit accumulator register during argmax. It no longer materializes
the 50,257-entry `lm_accumulator_i64` BRAM. The generated structural checkpoint
therefore falls from 39.3 Mbits / 144 memories to 36.1 Mbits / 143 memories,
without changing the signed-64-bit arithmetic contract. This is a capacity
optimization, not yet a fit result.

The authenticated Q8.24 token-embedding scales are a further exact capacity
optimization. Their values range from 14,525 to 105,952 and therefore fit in
signed 32 bits; the generated top stores the 50,257-entry table at 32 bits and
sign-extends each value to the existing signed 64-bit multiply before use (in
both embedding and logit scaling). The resulting Futil memory inventory is
97 memories / 34,448,640 bits (down from 36.1 Mbits), below the approximately
35.2-Mbit YPCB RAMB36-equivalent budget. This is a structural capacity result,
not a mapped-resource, timing, bitstream, or board-inference claim. Its
provenance receipt is `artifacts/reference/tinystories-1m-bram-scale-width-receipt.json`.

`scripts/pipeline/prepare_tinystories_1m_bram_image.py` now converts the
runtime-plusarg memory image into synthesis-visible static `$readmemh` inputs
and emits a hash manifest. The resulting SV was accepted by yosys-slang with
initialization enabled; the retained receipt is
`artifacts/reference/tinystories-1m-bram-static-image-receipt.json`. This is
image readiness only: the receipt intentionally does not claim a bitstream.

A bounded RAMB18/LUTRAM mapping experiment marked only the two largest MLP
weight memories as distributed and invoked the pinned `synth_xilinx` memory
stage. It did not emit a mapped report within the interactive observation
window and was terminated; no resource or timing claim is attached to that
experiment. The production RTL remains unchanged by it.

The model weights remain immutable BRAM initialization data. The JTAG bridge
has been linted with Verilator in `BSCAN_SIM` mode, and the production
generated SV still passes Calyx compilation and the focused lowering tests.

This is not yet a board-acceptance result. A real YPCB bitstream, timing report,
and three cold-start JTAG runs are still required before claiming board
inference. The bounded generated-SV execution was timeboxed at 90 seconds
without reaching completion, and the first full-top Yosys attempt did not
produce a report within the available synthesis budget. These are integration
blockers, not evidence of board inference or timing closure.
