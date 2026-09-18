# Compiler DDR3 queued-address reset experiment

The static-counter six-hour route ended with exit 124, without routed FASM,
routed JSON, or final timing. Its last logged queue had 94,834 arcs after
21,274.77 router seconds. The full log remains at
`/tmp/compiler-ddr3-route-6h.ZFiOPF/route.log`, SHA-256
`aa5f3ced552b70ca175da324b6e8e021bf1165ff726e7489208cdfca3540fa90`.
This is a timeout, not proof of unroutability or a final timing failure.

Read-only netlist inspection found 23,598 physical input-pin loads on
`rowstream_rst_n`, versus 19,603 in the static-wait placement whose full route
completed (but failed timing). In the current synthesis, 3,745 reset loads
belong to external request-address registers. This is a measured optimization
target, not proof that reset fanout caused the routing timeout.

The compiler external-memory cell now captures `queued_address` in a separate
reset-independent process when its local slot is empty. Valid/control reset,
request-index reset, response state, PCIe, DDR3, clocks and constraints are
unchanged. An address is captured on the enqueue edge and held while queued
or pending. Its invalid-cycle value is deliberately unspecified.

The structural regression failed on the prior resetful implementation because
Yosys inferred SRST on the address register. The new implementation passes.
A frozen compiler-cell reference (not kev-gpt) supports a Yosys induction
miter for WIDTH=8, IDX_SIZE=4, SIZE=16, BASE=19. It compares valid addresses,
done, read data and unchanged internal control/index state, assuming initial
reset only. Subsequent resets and all other inputs are unrestricted. The
internal-state assertions strengthen induction; they are not assumptions.
The initial output-only proof timed out at 90 seconds; the strengthened proof
passes. This cell proof does not qualify every full-model parameterization.

## Full-model result

The regenerated candidate from commit `949a528` completed the exact-image
first-token simulation with exit 0 (session 87519): token **11**, **165,090,998**
cycles, and **13,116,912** requests and responses. The complete run log is
byte-identical (`cmp` exit 0) to the preserved
`artifacts/diagnostics/2026-09-17-shared-ddr3-simulation/static-counter-run.log`.
This establishes identical logged checkpoints, not an ordered transaction trace.

- Generated model SHA-256: `daed4badbce39933ffbbec461fa40603ddfdec0d137f543132fd02fd7ec1d88a`.
- Simulation executable SHA-256: `5d4dd71e4c518a5bd3817070687a71a68cb0ca677af3bdc8111f1de1b5677208`.
- Run log SHA-256: `8825cbef981c840e113151902a39c72bbd646b85564614d494e2e6eec8f431db`.
- Input hex SHA-256: `52c169a96fa2218618b3ec845b6cb86c82ca70111e1c681bbb25533a38520141`.
- Prompt: `[7454, 2402, 257, 640]`; expected first token: `11`.

The command was `timeout --signal=TERM --kill-after=10s 10800
/tmp/compiler-ddr3-payload-reset.tywJVR/obj/Vcommand_integration_wrapper
+IMAGE=/tmp/compiler-ddr3-current.2Z9Mo4/tinystories-ddr3-lines.hex`.
The unchanged command-integration wrapper and driver are preserved beside the
static-counter log. This covers the real command adapter, backend, generated
compiler core and 240-port arbiter against a preloaded fixed-latency Wishbone
memory model. It does **not** cover PCIe loading, ownership arbitration,
physical DDR3/calibration, asynchronous crossings, or synthesis-only FSM
recoding. No board inference or full autoregressive claim follows.

Synthesis completed with zero check problems: 53,524 LUTs, 41,283 FFs,
245 DSP48E1, 47 RAMB36E1 and 7 RAMB18E1. Reset input-pin loads fell from
23,598 to 20,734, at a cost of 268 LUTs and 814 FFs. No-route placement
estimates still fail: rowstream 47.89 MHz versus 83.33 MHz required; PCIe
56.39 MHz versus 62.5 MHz required. These are not final routed timing.

The bounded three-hour seed-15 route remains running at this report's
checkpoint (session 28013). Completed routing, passing final timing and board
inference remain required before promotion. The previous pinned static-counter
candidate and loader baseline remain intact.

## Read-only critical-path investigation during routing

The no-route placement report identifies
`compiler_accelerator.core.compiler_core.context_tokens_read_data[13]`
to bank 137's `request_queued` register as the rowstream critical path:
1.5 ns logic plus 19.4 ns estimated routing. This is an estimate, not evidence
of the final routed critical path or proof that bank selection causes the
router's convergence difficulty.

Counting input-pin connections in the synthesized netlist (SHA-256
`739a784e287d157f61647afc597e62a7574aae1123be2d43cde007459cf64dd8`)
finds 197 token-bank `request_queued` nets. The context-token bits have the
following input-pin fanouts: bits 0–7 each 2; bits 8–9 each 398; bits 10–11
each 101; bits 12–13 each 18; bits 14–15 each 36. These are synthesized
pin loads, not placement distances or post-route delay measurements.

In particular, the reported critical source bit 13 is not the highest-fanout
source. Do not infer that merely reducing its fanout will fix timing. The
197-bank distributed decode/request structure is a concrete candidate for
further investigation if final routing fails; no selector-register insertion,
bank consolidation or other candidate modification has been performed here.
