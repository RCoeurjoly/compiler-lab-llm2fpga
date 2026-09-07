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

The banked static top passes the Yosys-Slang hierarchy/preparation gate at 242
memories and 35,158,330 structural memory bits. The corrected pinned
`synth_xilinx` coarse preparation completes in 311.86 seconds; the strict
map-memory result is 39 RAMB36E1 and 15 RAMB18E1 before final technology
mapping. The durable hashes and resource/placement diagnostics are in
`artifacts/reference/tinystories-1m-bram-production-synthesis-2026-09-07.json`.

The model weights remain immutable BRAM initialization data. The JTAG bridge
has been linted with Verilator in `BSCAN_SIM` mode, and the production
generated SV still passes Calyx compilation and the focused lowering tests.

## Banked-memory mapping checkpoint

The first coarse-to-memory-mapping attempt exposed the remaining capacity
problem: the vocabulary tables were represented as 50,257-word memories, and
the mapper left those memories unresolved. The compiler backend now banks the
token code table by 512 vocabulary rows (99 banks of depth 32,768) and the
32-bit token-scale table by contiguous 32K-word banks (2 banks). Address
selection is explicit in the generated Calyx and preserves the original
row/column ordering; the final scale bank boundary is bit 15, not the code
table's bit 9. Each bank-mux level now selects its own address bit (rather
than repeatedly selecting bit zero); the corrected Futil compiles through
Calyx, but the expensive coarse/map run must be repeated for a strict hash-
aligned mapping receipt.

With that change, the regenerated static image has 242 structural memories
and 35,158,330 structural bits. The pinned XC7 coarse pass completed in
432.67 seconds and the following `map_memory` pass consumed all banked token
memories into 39 `RAMB36E1` and 15 `RAMB18E1` instances. Only three small
scratch `$mem_v2` memories remain (`prompt_words` and two done buffers).
The corrected design was then rerun end-to-end through Yosys-Slang, XC7
coarse synthesis, memory mapping, technology mapping, and JSON export. The
hash-aligned map again consumed the banked memories, and the generated JSON
reached nextpnr packing. After legalizing generic boolean cells, the design
requires 628,976 `SLICE_LUTX` sites against 597,200 on the Kintex-7 (105.3%),
with 21,976 FFs, 38 RAMB36E1, and 14 RAMB18E1. Placement therefore fails on
genuine LUT over-capacity rather than BRAM capacity. A diagnostic run with
`--ignore-loops` reached timing-budget annotation but did not place the full
design. A bounded ABC optimization attempt on the generated `main` module did
not produce an artifact within the observation window. This is therefore not
a placement or timing result. The hashes and
exact residual-memory list
are recorded in
`artifacts/reference/tinystories-1m-bram-production-synthesis-2026-09-07.json`.

The omitted DSP stage was also tested explicitly. Unmapping the coarse
`$macc_v2` cells enables Xilinx DSP inference, but produces 2,433 `DSP48E1`
instances against 1,920 available on the device. Thus DSP inference alone
does not rescue the design; it moves the over-capacity condition from LUTs to
DSPs. The bounded receipt records this as a diagnostic experiment.

A second bounded experiment applies `simplemap` only to the large boolean
operators in `main`, followed by `abc -lut 6`. It reduces the mapped main
module's `$and/$or/$xnor/$mux` counts from 12,029/3,770/2,867/1,798 to
4,292/70/1,868/20 and emits 20,801 LUT nodes. This is a promising compiler
optimization direction, but formal equivalence and a complete resource run
have not yet completed, so it remains a candidate artifact rather than an
accepted datapath change.

The generated full-top Verilator run did not reach completion in the observed
35 million-cycle window and was stopped to avoid an unbounded run. This is a
simulation-throughput blocker, not an inference result.

This is not yet a board-acceptance result. A real YPCB bitstream, timing report,
and three cold-start JTAG runs are still required before claiming board
inference. The bounded generated-SV execution was timeboxed at 90 seconds
without reaching completion, and the first full-top Yosys attempt did not
produce a report within the available synthesis budget. These are integration
blockers, not evidence of board inference or timing closure.
