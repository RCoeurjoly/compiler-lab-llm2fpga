# Compiler TinyStories-1M two-token synthesis and route diagnostic

Status: **diagnostic checkpoint, not board acceptance**. The accelerator RTL is
compiler-generated; no kev-gpt accelerator RTL is used. The pinned model
package supplies authenticated weights, not implementation logic. This report
records the 30 MHz, BRAM/LUTRAM, JTAG-only two-token candidate. The accepted
first-token bitstream remains untouched.

## Passed gates

- The current generated-RTL harness returned `[11, 612]` on both independent
  reset/start runs, with exactly `185872559` cycles per run, indexed output
  readback and no context-feedback mismatch. Its receipt is
  `.superpowers/sdd/2026-09-09-tinystories-16-token-board/current2/production-execution.json`;
  event-log SHA-256 is
  `7d8c46354d81b1289a8afd1b9a6735227ef7b14d96af6de1402790bfb9ed06bf`.
  Generated Futil/SV SHA-256 values are
  `69ce8f774d78f9d301f621cd701c04f571b62d393b26fbeaf1f50c2be3d132ae`
  and `cee658e6c2f1c6f7f8bf2e9a4775f9f85767ae9b22993fc12099b5208956bc91`.
- The authenticated static image contains 89 compiler source memories. Its
  manifest SHA-256 is
  `d35934a9edc57bf4fd7d4cdb4569d105f73bdf43def8cbed07d22a59eb5b0728`.
  The Yosys frontend required only the existing `done_buf` normalization.
- Initial memory mapping completed 108/108 checkpoints, but that route was
  **rejected before placement**: the early no-FSM coarse helper ran `alumacc`
  before `synth_xilinx map_dsp`, leaving zero DSP48E1 cells. A corrected
  pre-DSP frontend retains 39 `$mul` cells, and the pinned Xilinx DSP pass
  with `xilinx_dsp.multonly=1` infers 225 DSP48E1 before coarse optimization.
  The compiler/board coarse netlist retains 190. The corrected 108/108 mapper,
  native RAM conversion, fine mapping and standard-ABC final synthesis all
  exited zero. Final Yosys `check` reported zero problems and no residual
  memories. Diagnostic frontend commit: `0dd1168`; 53 focused Nix tests pass.
- Corrected final JSON SHA-256 is
  `b9f3364b1e88a51e028587ed21bc0e4f70d68783ce48bef23dc0075bf3d0624a`.
  Its cell counts are 755 RAMB36E1, 88 RAMB18E1, 14,708 RAM64M and 190
  DSP48E1. Pinned nextpnr pack-only passed with checksum `0x0778a750`, four
  BUFGCTRL, one MMCME2_ADV and one BSCAN. Pack log SHA-256 is
  `c8545923823ea4f64205930dd6ee7d27f04ed22826f4456c517fcc2f54e7f961`.

## Routing result and comparison

The one low-priority heap-placer/router2 attempt used the unchanged board XDC
(SHA-256 `4213bcdb0907f052dd76bffe6a8483e6e3e2b371aaa92ec12fbb26c923217320`),
`--freq 30 --seed 15 --no-tmdriv`, a 12 GB virtual-memory cap, and a 2400-second
deadline. nextpnr-xilinx and chipdb SHA-256 values are respectively
`25c434b7614ade7cbdd448b4f993d1feced26296b0164f6e648ddaced7ebac16`
and `d8472bfcc19dc31686d80cc34f0d37b958c268656182537b06b3439711b105f1`.
Placement completed and estimated accelerator Fmax at 35.06 MHz on covered
paths. Router2 then reduced overused resources from 161868 to 28768 to 6576
across three iterations but did not reach zero before `timeout` exited 124.
The route log SHA-256 is
`5ff60fbcabd273e251a966a285d51bef3ed6c3ff1367d28dcb90c2f2292c887b`.
There is **no routed JSON, FASM, bitstream, board inference or post-route timing
claim** for this candidate. BRAM/DSP timing coverage also remains incomplete.

The accepted first-token route is a useful control, not a substitute result.
This two-token placement's final wirelength was 6,884,338 versus 4,629,535 in
that control, and initial routing overuse was 161,868 versus 108,296. Both
netlists have 16,386 input sinks per c_fc/c_proj weight-ROM read-address bit;
that high fanout alone therefore does **not** localize the new routing slowdown.
The two-token netlist has 44 nets with at least 1,000 sinks versus 34 in the
archived first-token JSON, but fewer nets above 10,000 sinks (13 versus 19).
No compiler banking change is justified from this histogram alone. A bounded
SA-placer comparison was terminated early at about 10,000/165,960 initial
cells because it could not reach a placement result within its 15-minute cap.

Next gate: obtain a legally routed, timing-reported two-token bitstream from
this exact corrected JSON, then independently program SRAM and require
`[11, 612]` after one START. A longer deterministic route or a separately
evidenced placement/backend change is needed first. Neither the simulation nor
pack-only pass can be counted as board inference. Repository-wide tests remain
historically red/timeboxed; this is the user-approved diagnostic checkpoint.
