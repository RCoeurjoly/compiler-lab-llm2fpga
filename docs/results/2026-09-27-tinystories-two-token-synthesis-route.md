# Compiler TinyStories-1M two-token synthesis and route diagnostic

Status: **routed bitstream produced; hardware CSR failed before START; not board
acceptance**. The accelerator RTL is compiler-generated; no kev-gpt accelerator
RTL is used. The pinned model package supplies authenticated weights, not
implementation logic. This report records the 30 MHz, BRAM/LUTRAM, JTAG-only
two-token candidate. Earlier no-route statements below describe historical
attempts; the final section supersedes them. The accepted first-token
bitstream remains untouched.

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

This first-token control is **not** an isolated test of token feedback. The
accepted board source (Futil SHA-256
`e422c0093658d376e23510dea1a8375a87c0df10292d9a237454c862dc49fecc`)
declares 296 external memories and 35,027,168 logical bits, including 197
separate INT8 token-code banks. The current two-token source (Futil SHA-256
`69ce8f774d78f9d301f621cd701c04f571b62d393b26fbeaf1f50c2be3d132ae`)
declares 118 external memories and 32,849,120 logical bits, including 25
packed 64-bit token-code banks. It also applies explicit lifetime reuse and
narrower stored scale words. These source-architecture changes confound any
first-token-versus-two-token routing comparison. In contrast, freshly
regenerated *current-compiler* one- and two-token sources have identical 118
external-memory declarations and 32,849,120 logical bits; their Futil hashes
are `a390eb19ba739018ddb1a7f9962db7c119c119a9d543dd9793b2f8cbb60539bd`
and `69ce8f774d78f9d301f621cd701c04f571b62d393b26fbeaf1f50c2be3d132ae`.
A controlled synthesis/place/route comparison within this current architecture
would be needed before attributing the slowdown to the added token step.

Next gate: obtain a legally routed, timing-reported two-token bitstream from
this exact corrected JSON, then independently program SRAM and require
`[11, 612]` after one START. A longer deterministic route or a separately
evidenced placement/backend change is needed first. Neither the simulation nor
pack-only pass can be counted as board inference. Repository-wide tests remain
historically red/timeboxed; this is the user-approved diagnostic checkpoint.

## Checkpointed placement diagnostic

A bounded placement-only replay of the same final JSON, XDC, seed 15,
30 MHz target, and `--no-tmdriv` settings completed successfully. It reproduced
the pack checksum `0x0778a750`, placed checksum `0x7dc024d1`, SA wirelength
6,884,338, and covered-path accelerator estimate 35.06 MHz from the original
attempt. The resulting reusable placed JSON has SHA-256
`fd1f1b3b3b8233ef5b728b2129673c1bc0e18677cf217dd04c882d618a53ce92`.
A `--no-pack --no-place --no-route` reload exited zero with the same primitive
utilization. This is a placement checkpoint, not a routed result; its purpose
is to isolate router cost without rerunning synthesis or placement.

The checkpointed router2 continuation used that exact placed JSON, the same
XDC, 30 MHz target, seed 15, and `--no-tmdriv`, with packing and placement
disabled. It ran low priority under a 12 GB virtual-memory cap and a bounded
3,600-second timeout. It exited **124** after six iterations. Overused routing
resources fell `161614 → 28730 → 6524 → 3591 → 2832 → 2462`, but never reached
zero. Its log SHA-256 is
`182f517db0f2aa00ba7495ddbc4e56e5a0364d32e14592ccd854a3bfd25f2d2a`;
the placement-only log SHA-256 is
`0943cf24e8a0ef732a8004c2c1404b467554d0da80e7f9d39b7f0d5978b8aaba`.
No routed JSON or FASM was written. This rules out merely repeating the same
placement with a modestly longer router timeout as a fast route to board
inference; it does **not** prove the design is unroutable. The next controlled
experiment should change one evidenced placement/router variable, compare
wirelength and early overuse against this checkpoint, and retain the exact
model, fixed-point arithmetic, 30 MHz constraints, and seed 15. No speculative
compiler-bank rewrite is supported by these results alone.

## Router and placer-control localization

The pinned nextpnr binary comes from Nix derivation
`fc75my8285h9bkcbwcqf0l2qpzpiq8w3-nextpnr-xilinx-0.8.2.drv` and source
`rzmrkc8aff649333zc7rfc6pdzmsimqy-source`. This identity matters: the
working checkout of nextpnr has newer, unbuilt edits and is **not** the
executable used for the preceding route. The derivation's Kintex `Arch::place`
hard-codes HeAP `alpha=0.08`, `beta=0.4`, `hpwl_scale_x=1`,
`hpwl_scale_y=2`, `spread_scale_x=2`, and `spread_scale_y=1` after reading
generic placer settings.

Two controlled router probes used the exact placed checkpoint. First,
`--router router1` alone still entered router2: loading the placed JSON restored
its saved `router2` setting after CLI setup. The pinned Python binding lacks
`ctx.setSetting`, so a pre-route hook cannot change it. A copy of the placed
JSON with its **sole** router setting changed to `router1` was reversibly
verified against the original SHA-256. This time nextpnr actually entered
router1 and reported 685,780 arcs. The run was stopped with SIGTERM (exit
143) after approximately 315 routing seconds: it had processed 134,000 arc
attempts and still reported 602,479 remaining. It cannot complete the
15-minute diagnostic bound at that observed rate. Its log SHA-256 is
`39800ffdd5cc82cc90f10262d46e1d41519bccc32a78e1a335fe7b945ed6ae2f`.
There is no routed artifact from either probe.

Three one-variable placer-input probes retained the exact synthesized cells,
seed, XDC, and 30 MHz target. Adding generic `placerHeap/alpha=0.05` completed
placement, but its entire iteration sequence, SA wirelength 6,884,338, and
all 165,972 cell-to-BEL assignments matched baseline exactly. Its log and
placed-JSON SHA-256 values are respectively
`3c55d5d5c476f99fc37a7490ec0b038f5cadafd0cdc0a83917e29d45645e4716`
and `a5731da46139c3c3870f5de664ecaa9479d282d12a8dea4938aaa91d9c3ed046`.
`placerHeap/beta=0.8` and `placerHeap/hpwlScaleY=1` were each terminated after
seven analytical iterations because every reported solved/spread/legal wirelength
was identical to baseline. Their partial-log SHA-256 values are respectively
`4d79a6106888810c1f4527ba2b673aad9d3ac63856f0abbcc0a8f8f0c6fc0b81`
and `ad659289ba1a2ca7596add338c5dec0028faed50d062f527fcfad4fac4b98c30`.
The source-level Kintex override explains why these JSON settings did not
exercise the intended heuristics. They are invalid as evidence for or against
the numerical parameter choices themselves.

The next backend step should preserve the validated binary and build a
separately named Nix diagnostic variant that makes the Kintex geometry
parameters configurable while retaining their current defaults. Only a
verified change in cell placement and early router2 overuse would justify a
full routing retry. No accelerator arithmetic, model memory, or board image
was changed in these diagnostics.

## Isolated Kintex geometry diagnostic

The separately named `.#nextpnr-kintex-geometry-diagnostic` Nix package pins
the historical nextpnr source and build settings, then applies only
`0038-allow-kintex-heap-geometry-diagnostic-overrides.patch`. It does not
replace the production tool. The initial patch tried to reuse generic
`placerHeap/alpha` and `beta`; nextpnr's generic constructor had already
populated those keys with 0.10 and 0.90. Its first analytical iteration
diverged from the historical control, so that invalid run was stopped. The
corrected patch uses separate `kintexHeap/*` keys with the historical Kintex
defaults. Three focused tests and the Nix package build passed.

The corrected tool (binary SHA-256
`07577e755556cfe04f4932b83c95e16dc38dd918ec13371556374e1ec5df2ecf`)
placed the exact final synthesized JSON (`b9f3364b...`), historical chipdb
(`d8472bfc...`), board XDC (`4213bcdb...`), seed 15 and 30 MHz
`--no-tmdriv` setting. With no geometry override, it reproduced pack checksum
`0x0778a750`, final placement checksum `0x7dc024d1`, 6,884,338 SA wirelength,
35.06 MHz covered-path Fmax, and all 165,972 `NEXTPNR_BEL` assignments of
the historical placed checkpoint. The JSON files are not byte-identical
because the diagnostic tool records its six default `kintexHeap/*` settings.
The new control placed JSON and log SHA-256 values are
`f4534ac4dc7af8a2af20c624737b3702b03a824842025a02ca9da1b52f681ece`
and `67342c48d709cfcbe4db8c659e396aba30a6d123d498814d248f3af578675697`.

One changed input set only `kintexHeap/hpwlScaleY=1` (instead of 2), keeping
the model, synthesized cells, chipdb, XDC, seed, and clock target fixed. Its
input JSON SHA-256 is
`8b229c73e62f854760f4a5cb9ea9c896a67ee816741b1aaaf3af2c1348a2acb6`.
Placement completed with checksum `0xd11cb119`, 165,014 changed
`NEXTPNR_BEL` assignments, and 37.59 MHz covered-path Fmax. Its placed JSON
and log SHA-256 values are
`53f954273a5c7d5296b308ececfd03986d18baaa56c994ec677e2031640a7ef9`
and `2042c21f654542522f056d79f763fe6e6273cc5f30a3fdd06b47923ada424c14`.
The placer wirelength objective uses different vertical scaling, so its raw
number is not directly comparable with the default's.

An identical-binary router-only control hit a 300-second cap before its first
iteration. The changed placement's router2 run, also under a 12 GiB memory
cap, was stopped immediately after iteration 1: 3,879,626 wires, 152,091
overused resources, total overuse 184,150 (log SHA-256
`563e6f0bc099c1b6ad60d7a8e6740a7c54d213bf377867dc9227e6cc37bab832`).
Against the *historical* router-only default placement, iteration-1 overused
resources decreased from 161,614 by about 5.9%, and total overuse decreased
from 196,129 by about 6.1%. This comparison is qualified: the placements
were proven identical, and the router source was unchanged, but a paired
iteration-1 measurement with the diagnostic binary was not obtained. A modest
early congestion improvement and placement timing estimate do **not** establish
route convergence, post-route timing, a bitstream, or board inference. The
geometry probe is diagnostic evidence, not a production backend change.

## Current-compiler one-token physical control

The archived accepted first-token bitstream uses a different compiler memory
architecture, so it cannot isolate token feedback. A fresh current-compiler
`generation_steps=1` control instead used the same authenticated 89 source
images, 108 flattened mapped memories, pinned Yosys/nextpnr/chipdb, XDC,
seed 15, 30 MHz target, `--no-tmdriv`, and memory-mapping policy as the
current two-token candidate. Its Futil hash is `a390eb19...`; its generated
RTL simulation passed two independent reset/start runs, each selecting and
returning token 11 after 92,936,279 cycles. The simulation receipt SHA-256 is
`824bada41497a04635b3402999076b76664273b9313cc94261017a58d9914ad5`.

The one-token final Yosys JSON SHA-256 is
`b1a1de9f8358a99a5825240d0aacbb7e4932737f774fb0702c6afcbbf9bda5e9`.
It contains the same 755 RAMB36E1, 88 RAMB18E1, 14,708 RAM64M, and 190
DSP48E1 as the two-token netlist. Pack-only passed with checksum
`0xbdbafda0` and 137,561 SLICE_LUTX, versus 137,604 for two tokens.
Default placement completed with checksum `0xa25fd82d`, 6,977,810 SA
wirelength, and a 31.58 MHz accelerator estimate on covered paths, versus
6,884,338 and 35.06 MHz for two tokens. Its placed JSON SHA-256 is
`bcbe8bd2255d2e6e2662151a167c5dd5f9bceacec7023bd89a0090c499af383c`.

A router-only continuation from that placement, capped at 900 seconds and
12 GiB of virtual memory, exited 124 after iteration 1. It reported
3,907,568 wires, 162,752 overused resources, and total overuse 208,317;
the comparable two-token placed-checkpoint iteration 1 reported 161,614
overused resources and total overuse 196,129. Router log SHA-256 is
`a1a898ccf5748000649ccbff441947518a1c813ffd84ce0b96f35373eed3c00e`.
There is no one-token routed JSON, bitstream, or board result from this
control. Removing the second-token feedback did not reduce *initial* routing
congestion in the current architecture; this does not prove either netlist
unroutable or identify the underlying net/region bottleneck. A subsequent
backend change should therefore target measured shared congestion rather
than attributing the slowdown to token feedback alone.

## Geometry-controlled legal route, bitstream, and first hardware boundary

The separately named geometry-diagnostic nextpnr binary (SHA-256
`07577e755556cfe04f4932b83c95e16dc38dd918ec13371556374e1ec5df2ecf`)
continued the same two-token placed checkpoint with only
`kintexHeap/hpwlScaleY=1` changed. Its router2 overused-resource counts fell
`152091 → 22722 → 3162 → 1344 → 983 → 834`, then reached zero at iteration
40 with `archfail=0`. The router1 legality check and post-route legalization
completed, and nextpnr exited zero. The routed JSON SHA-256 is
`3546cfb3b71889a68d7d708fdb70ae290a8c2801a782caab5d0d80036fcec66c`;
the first route log SHA-256 is
`b29f33f0829ac26ebbbea067fa03e06c973af608ca3a324b5cacd17cdfaa6a26`.
Covered-path accelerator Fmax was 39.56 MHz against the unchanged 30 MHz
target. BRAM/DSP timing coverage remains incomplete, so this is not full
timing qualification.

Reloading the routed JSON in this pinned nextpnr crashes before FASM emission:
`BaseCtx::attributesToArchInfo` calls `Arch::getPipByName`, which throws
`std::out_of_range` for a saved route PIP. Source inspection shows the writer
uses `source->destination` names while the importer expects the older tile/index
form. No routed JSON was edited to mask this. Rerouting the identical placed
checkpoint with `--fasm` in the same process exited zero, reproduced the routed
JSON byte-for-byte and the 39.56 MHz estimate, and emitted FASM SHA-256
`3de464ea452ac4a7f84705c672a9d5bdc779ef9fea0328c31148b71f5d887aa3`
(route log SHA-256
`17ca7cfa8fb1e262dc6d9f40ba6c159eb47e7ae6b06f0d5e1f48cc38ded0c8a0`).
The repository's `fasm2frames → xc7frames2bit → bitread` gate exited zero with
the exact `xc7k480tffg1156-2` part. The USER1 BSCAN feature is present in
FASM and its expected bit is set in the decoded configuration frame. Bitstream
SHA-256 is
`a45e654a942f28f2d5006dad680c43cb240c463393a13fba4ddaf052260f0ec6`.
These ignored working artifacts are under
`.superpowers/sdd/2026-09-09-tinystories-16-token-board/kintex-geometry-20260927/`.

The identity-checked Helios isolation helper removed the live PCIe endpoint
before sudoless HS3 SRAM programming. Programming this two-token bitstream
exited zero with `isc_done=1`, `init=1`, `done=1`. The canonical Nix/JTAG
generation checker then failed **before START**: after reset, STATUS returned
`0x1400000000000000` rather than `0x2800000000000000`. No prompt was loaded
and no token inference was attempted. The raw receipt SHA-256 is
`b9e21a030fec919f0bc81e936470541928c74ee65b76a55cd3e5f42d90c4db51`.

As a same-cable control, the authenticated accepted first-token bitstream
(SHA-256 `2e28abb6638b407fd55b681018275c712afe47fde2de24ba8d1ebe584208b91a`)
was reprogrammed into SRAM. Its established checker passed, returned exact
token 11 in 3.18 seconds, and observed the correct `0x28…` STATUS prefix
(control receipt SHA-256
`162bbbf025ba2c8714933d22bbc066902e6a038a3a5358126b0e528644b93ea4`).
The accepted CSR source captured the unshifted response word; the current CSR
preloads a one-bit right-shifted word. This is a specific, testable explanation
for the observed half-value, not yet a verified hardware fix. An existing
`BSCAN_SIM_PHYSICAL` replay does not reproduce the exact hardware transaction,
so the CSR change must pass a targeted red/green bit-level test and a newly
routed board gate before accepting `[11,612]`. The current board image is the
accepted first-token control, not the failed two-token candidate.

## Opt-in router2 congestion attribution

An isolated nextpnr package added an opt-in iteration-1 report to router2;
the production package and routing decisions were not changed. The diagnostic
binary SHA-256 is
`98134bc08a32a19ee141169dde79707ab9046c0ddccd014fdb81c09c915b4889`.
The input was the original **default** two-token placed JSON (SHA-256
`f4534ac4dc7af8a2af20c624737b3702b03a824842025a02ca9da1b52f681ece`)
with only `router2/diagnosticIter1=1` inserted; deleting that line reproduced
the original file byte-for-byte. The router used the same chipdb, XDC,
30 MHz target, seed 15, and `--no-tmdriv`, under a 12 GiB virtual-memory cap.
It was stopped after iteration 1, not used to produce a routed bitstream.

Iteration 1 reported 161,614 overused wires and 196,129 total overuse,
matching the historical default-placement measurement. The heatmap sums to
exactly 196,129. The largest single 10×10 coordinate bin (x=260–269,
y=190–199) contains 1,205 overuse, about 0.61% of the total. The leading
ranked nets by count of shared wires were a mapped `$techmap` net (474),
`reset` (348), `c_proj_weight_codes_i8.read_addr[8]` (344),
`c_fc_output_q16_16.read_addr[8]` (328), and
`lm_gemv_weight_address_out[15]` (248). These are contributors, not proof of
one local or single-net root cause; congestion is distributed. The diagnostic
log and heatmap SHA-256 values are respectively
`15f56cccb9fc255c204d7d48b93e3d2c577f93f37d1d991526c534e7c45fc742`
and `457835b7f1943a8bee46e923b7e53268f9fd5d44258ad128af6e9ec1b8edfb97`.
The checker passed on the real report and rejected a deliberately corrupted
heatmap. The immediate inference blocker remains the physical CSR response
alignment, not this now-routed placement.

## Exact two-token CSR raw-vector A/B

The same routed two-token bitstream (`a45e654a942f28f2d5006dad680c43cb240c463393a13fba4ddaf052260f0ec6`)
was reprogrammed into SRAM with Helios still deauthorized. The existing
canonical HS3/MPSSE raw-vector probe used USER1 (`0x02`), 1 MHz, TDO bit 7,
negative-edge drive, and three 64-bit loopback transactions for
`0x7123456789abcdef`. The first returned zero (pipeline fill); the following
two returned the identical `0x3891a2b3c4d5e6f7`, exactly the command shifted
right by one bit. Raw individual TDO bits are retained in
`board-two-token-raw-loopback.json` (SHA-256
`bcfc3d61155b59fc2ba7b100bfd9f2855c5e86f31f9120af3eaf908dc2dc1d20`).
The canonical generation checker on this fresh SRAM configuration again
failed before START at STATUS: expected `0x2800000000000000`, observed
`0x1400000000000000`; receipt SHA-256
`ac0a68f6ca53942ec97007791bb253bf93c6dd9cddd93757a4d5fd41dd6bd85b`.
Thus both a high-entropy response and STATUS exhibit the same right shift.

The accepted first-token bitstream (`2e28abb6638b407fd55b681018275c712afe47fde2de24ba8d1ebe584208b91a`)
was restored and its established checker again passed exact token 11 in 3.21
seconds, on the same cable and transport (control receipt SHA-256
`d3dcbfcef44609e5541c93774f591e57c8f3d3471b8792525c63b539c78f5055`).
The board is left with this accepted SRAM image. The current physical CSR
capture preloads `response_word >> 1`; the accepted CSR captured the unshifted
word. That difference directly predicts both observed half-values. However,
the September 11 CSR-only experiment found that removing this preload did
*not* pass its full protocol on a different image. Therefore the present
evidence localizes the immediate two-token response mismatch, but does not
establish that a preload-only edit is sufficient. A corrected candidate must
first reproduce the raw-vector behavior in a bit-level test, then pass the
complete reset/status/prompt/readback/START and `[11,612]` board gates.

## Existing CSR test reproduces the first hardware mismatch

With the current, unmodified CSR source (SHA-256
`1f997db3ab0522d7a3d9420ea7b2050a48d38e4c4055a73dc807584078a5847e`)
and existing full CSR testbench (SHA-256
`c829fdc52851a15132b3346e7365b221332453d7a9e9ee4fff6a3c8445cf4dc7`),
Icarus 13 (binary SHA-256
`5553e9ceab3b9e1af68480f7c5bf7fe71641d51f1218aa492137a9acba224c7b`)
passes the ordinary `-DBSCAN_SIM` prompt/readback/reset/START test. Adding
only `-DBSCAN_SIM_PHYSICAL` to that compile fails at the test's **first STATUS
capture**: expected `0x2800000000000000`, actual `0x1400000000000000`.
The latter is the exact first failure observed on this two-token bitstream.
This is a targeted simulation reproduction, not yet a verified correction;
the earlier September 11 physical-boundary replay modeled a different image
and did not reproduce that image's full transaction behavior.
