# First-token prompt ABI repair

The first-token goal uses the full compiler-generated TinyStories-1M model,
BRAM only, the validated 30 MHz clock, and the existing 64-bit USER1 transport.
The authenticated prompt is `[7454, 2402, 257, 640]`; its first reference token
is `11`. The existing fixture verifier passed for artifact
`31fbd1e3f5b13d7b07466a72e9c6a551ffc00bd4fee375241f095ba5b5cda677`.
This check did not perform a fresh eager-model replay.

## ABI change

Prompt writes (opcode 1) now use command bits `[17:16]` for the index and
`[15:0]` for the value. Opcode 6 reads the stored word at index `[17:16]`,
returning its value in response bits `[15:0]` with upper bits zero. Read all
four words after writing all four; write echoes alone cannot prove storage.
Opcode, shift order, TAP sequencing, status, reset, start, and token-read
semantics are unchanged.

This is incompatible with the former overlapping index in `[5:4]`. The v2
host checker requires the rebuilt image; do not run it against the accepted
v1 CSR bitstream and mistake an ABI mismatch for hardware regression. The
historical v1 receipts and accepted bitstream remain unchanged.

## Verification

The actual CSR RTL test failed before the repair: the frozen prompt was stored
as `[640, 7454, 2402, 0]`. After the repair, three write/readback/reset sequences
passed with the BSCANE2-gated DRCK model. The test checks both core-facing
prompt wires and serial readback of every stored word.

The host regression failed against the revised device ABI before its repair.
Afterward, 23 tests passed across `tests.test_tinystories_user1_check`,
`tests.test_tinystories_1m_bram_production`, and
`tests.test_tinystories_1m_bram_image`. A negative host test rejects successful
write echoes when storage is lost. The host checker never issues START.

## Remaining acceptance

The compiler now accepts `generation_steps=1` or `2` (default `2`) through
`generate_production_kernel` and `generate_model_kernel`. It rejects other
values, including booleans and non-integer lookalikes. The one-step output
differs from the two-step Calyx text only in `model_step_lt.right`: `2'd1`
instead of `2'd2`. Source-memory descriptors and oracle identity are unchanged;
the provenance records the selected execution length and real context lengths.
The existing audit-generator Futil hash regression also passes. All 25 targeted
tests passed after this change. This is generator verification, not execution.

The simulation runner accepts `--generation-steps 1`, retains default 2,
records compiler provenance, checks observed token commits, rejects commits
beyond the requested execution length, and compares the public `token_id`
port as well as stored selected tokens. Executable C++ checker tests use a
controlled model-port fixture: they are checker tests, not model inference.
All 29 targeted tests passed. The full one-step model also lowered to SV in
1.47 seconds (Futil SHA-256
`55b2ae5a55e7c1931ca627655e48dbafc2c272144f08c48f349a6c23a4160b52`).

The static-image builder also accepts `--generation-steps 1` and binds its
manifest to that schedule's Futil and oracle hashes instead of silently using
the two-step default. Its new test materializes all 240 real immutable source
memories into a temporary image and checks the manifest; the test's SV skeleton
only exercises initialization and is not an inference design. All 30 targeted
tests passed.

The full-model SV run is in `/tmp/tinystories-first-token-sv-20260908`, with log
`/tmp/tinystories-first-token-sv-20260908.log`, under a 1,800-second outer bound.
It failed with token 0 at cycle 92,688,197; expected token 11. The first-run
failure is preserved. No second run or board test passed.

Full generated-SV execution, a new physical build, and three
independent FPGA reconfigurations with exact first-token inference remain
unperformed. No inference success is claimed. Accelerator timing coverage
remains incomplete; functional success will not imply full timing qualification.

## Hardware checker preparation

`scripts/pipeline/infer_tinystories_first_token_jtag.py` verifies the frozen
oracle before opening JTAG. It resets the TAP once, writes and reads all four
prompt words, issues START once, polls busy/completion with a maximum
300-second deadline, and checks token zero. Failures preserve transaction
history; there is no automatic retry or reset after START. The receipt includes
oracle, checker and transport hashes plus its own hash. It explicitly does not
establish independent FPGA reconfiguration or bitstream identity; those must
be bound to the programming evidence during hardware acceptance.

Four controlled-device tests exercise success, bad prompt readback, wrong token,
and timeout. All 34 targeted tests pass. The checker has not been run against
the board, which still holds the previous CSR-only-validated image.

Fresh full-top elaboration also passed with 266 memories, one BSCANE2, two
BUFGs and one MMCME2_ADV. The new RTLIL hash is
`ab39e8ce2ccf6c16f604899d506e00d09d96bf65493bb9f42c23b8291d21f14d`.
All 240 static source image records and file hashes match the accepted baseline.
Memory mapping uses the fresh `/tmp/tinystories-first-token-map-20260908`
checkpoint directory; it does not reuse earlier top-level RTLIL snapshots.

## Localized memory-latency repair

The failing model's embedding output matches the authenticated hash
`1d6a6b51026506667795de7fd0c4b5d94646aa066b4f7cfe37e69b28829bbcde`
at cycle 8,344. Block 0 diverges, and its first LayerNorm output already differs
at cycle 55,071 (observed `bb3087ad033687d744b6576a9744a17f82b7156b3955dc5ce80858166708b95d`).
The attention fixture verifier passed before comparing its LayerNorm values.

The unchanged compiled model's cycle trace shows a read of address 1 at cycle
8,367, followed by accumulation at 8,368 while read data is still 17646 and
`done` is low. Every column contributes 17646; the sum becomes 1129344.
Calyx declares `seq_mem_d1` with `@interval(1)`, while the production SV
post-pass inserts an address register and delays `done`: a two-cycle operation.
Static scheduling consequently consumes the data too early.

Production compilation now creates a private Calyx-library overlay declaring
`seq_mem_d1` as `@interval(2)` before scheduling. The installed library and
memory RTL remain unchanged. Small one-cycle memories retain their result
through this conservative two-cycle schedule. A hashed overlay receipt binds
the original and replacement declarations, and successful execution receipts
bind that receipt. Use the production runner to compile the staged-memory
image; bare generic Calyx lowering is not equivalent.

The permanent regression compiles the first four real embedding values through
Calyx and the production memory post-pass, then executes the SV with Icarus.
The original declaration fails; the corrected declaration produces exactly
`-4243`. The test also verifies the installed declaration is unchanged. All 35
targeted tests pass. This proves the focused repair, not full-model inference.
The candidate physical build was stopped after the original simulation failure;
its partial checkpoints remain preserved and must not be reused for the repair.

## Narrowed GEMV scale connection (September 9)

With the latency correction, the first LayerNorm now matches the authenticated
hash `31f31df11ae9bf6e0ccf1df09b98157a8723c4684c5ce96c673683687bb0ef34`
at cycle 57,199. Q-input quantization also matches exactly. Q-output and its
MAC accumulator are zero, however; weight and output scales match the fixture.

Inspection of the generated Futil identified an undriven
`q_gemv_scale_signed.in`. The narrowed GEMV generator instantiated the adapter
and consumed its output without connecting the activation-scale memory. The
wide path bypasses that adapter. The production fix adds that one connection
inside the consuming group; the wide-path Futil hash remains unchanged.
Production provenance now acknowledges changes to an existing arithmetic
generator instead of retaining its previous blanket denial.

An executable Calyx/SV regression uses the first four actual query-input codes,
activation scales and weight codes. The unfixed narrowed MAC yields unknown
data in Icarus; the corrected MAC and all 16 test output entries equal the
hand-derived signed result `-3046697736`. All 36 targeted tests passed before
full-model revalidation. This does not claim that query projection or inference
has passed on the repaired full model. The obsolete latency-only full run was
terminated after localizing this second defect, with its artifacts preserved.

## Core START handshake

The scale-connected full-model replay now matches Q-input, Q-MAC accumulator,
and Q-output fixture hashes exactly. Block 0 still differs and remains under
checkpoint investigation; there is no full-token success claim.

A separate bounded replay used the board CSR's one-cycle START pulse: it did
not reach the embedding checkpoint within 100,000 cycles. The otherwise
identical replay with START held high reached the exact embedding checkpoint
at cycle 8,871. The Calyx top requires its go input held through execution.

The CSR now retains `core_start` after the existing one-cycle valid/start
ordering delay and releases it on completion or reset. No JTAG opcode, packet,
clock, or CDC transport change is involved. The actual CSR RTL regression failed
with the pulse implementation and passes with held START, completion/status,
token readback and reset cancellation. All 36 targeted Python tests also pass.
This repairs the internal integration handshake, not an observed board run.

## Softmax denominator scheduling

The scale-connected full run selected incorrect token 47208 at cycle 93,146,543.
Checkpoint replay established exact Q/K/V, attention scores, maxima, deltas,
exponentials and weighted numerators. Comparisons project the eight-row/key
storage onto the four real tokens before checking the fixture. All 64 real
denominators differ: the first is 2097152 instead of 1048576. This halves the
first context value (-686 instead of -1371).

The cause is the combined `causal_write_exp_accumulate_denominator` group:
its register self-add runs for both cycles of the memory write. Production
lowering now separates the memory write from a one-cycle register accumulation,
keeping the same probability expression in both groups. The audit path remains
unchanged. The executable regression extracts these actual generated groups;
the original schedule reproduces 2097152 and the repaired schedule yields
1048576 with the probability memory write intact. All 37 targeted tests pass.
Full attention/block/token verification of this repair remains pending.

### Repaired full block verified

The full-model replay at `/tmp/tinystories-first-token-denominator-20260909`
now produces the exact block-0 output at cycle 6,270,512, SHA-256
`61a7016bc7936ae32cefdf8153cf4560454c662e6c0ea6351144f3a5b377bedf`.
All eleven captured intervening checkpoints match authenticated attention/MLP
fixtures: K, V, attention context, output projection, attention residual, ln_2,
c_fc input, c_fc output, GELU output, c_proj input, and c_proj output.
The diagnostic links the same compiled full-model archive as the ongoing token
run; it adds no RTL and supplies no intermediate model state.

The selected Futil, generated/static SV hashes, manifest self-hash and all 240
immutable images were independently checked before starting fresh elaboration
in `/tmp/tinystories-first-token-denominator-static-20260909`. The immutable
image records still match the accepted baseline exactly. Full-token simulation
and physical implementation remain pending; there is no board inference claim.

## All transformer blocks and final normalization verified; LM-head localization

The unchanged denominator-repaired full SV still selects token 47208, not 11,
at cycle 93,137,327. Its fresh diagnostic replay captured all eight block
outputs; every little-endian int64 hash matches the authenticated model oracle.
Final normalization also matches exactly:
`c90397ce02472db5514d53347061a8d181cfbec7b18bfbdf7ac829a8f0352e57`.
These are full-model executions from immutable inputs, not injected intermediate
states. Captures are in `/tmp/tinystories-first-token-denominator-20260909/`
(`block-N-step0.bin`, `final-ln-step0.bin`, `final-head-diagnostic.log`).
Physical synthesis was stopped and its partial checkpoints preserved after the
wrong token was observed. No replacement bitstream has been programmed.

The production LM-head schedule ran the entire GEMV vocabulary loop before
scanning logits, although it stores only one scalar accumulator. Consequently,
every token's scale consumed the last vocabulary accumulator. The replay's
final accumulator is -54819352379; token 47208 has the smallest weight scale,
consistent with this erroneous scale-only argmax.

An executable regression extracts the actual generated LM-head control and
restricts it to four entries, with hand-derived logits [64,384,448,-128]. The
old schedule selects entry 0 rather than entry 2. Production orchestration now
consumes each accumulator (scale, round, compare) inside the GEMV output loop,
before advancing to the next vocabulary index. The same regression now selects
entry 2. The non-production audit path remains unchanged.

The regression explicitly pins its bank selector to bank zero to isolate
scheduling from a second discovered issue: the generated bank-selection address
is driven only in the operand-read group, although its mux is consumed during
the later multiply group. Without that fixture isolation, Icarus produces an
unknown accumulator and stalls in the comparison. This bank-selector lifetime
issue needs its own executable regression and repair; the passing argmax test
does not establish that the unmodified banked LM head works. Full-model/token
revalidation and all three board runs remain outstanding.

All 38 targeted production, arithmetic, memory-latency, static-image, harness
and JTAG Python regressions pass with the argmax scheduling repair.

## LM-head bank-selector lifetime repair

Removing the explicit bank-zero fixture override reproduces an unknown
accumulator at vocabulary entry zero (`row=0 output=0 k=64 acc=x`), followed
by a stalled comparison in Icarus. Input code and activation scale remain
known (1 and 16777216). The bank mux is continuously connected, but its
address inputs previously existed only within `lm_gemv_read_operands`; they
were undefined during the later multiplication group.

Banked GEMV generation now places the ten weight-address-cone assignments
outside the read group. The existing output and k counters remain stable from
read through multiplication and accumulation. No memory primitive, latency,
numeric operation, unbanked/audit path, or transport is changed.

The previously failing unpinned-selector regression now selects the expected
token. A second bounded regression executes real vocabulary addresses 252..259,
crossing the 256-token physical weight-bank boundary, and correctly selects
258 from logits [0,0,0,0,64,384,448,-128]. Only the fixture's initial output
counter and loop limit are bounded; the generated bank addressing, reads,
arithmetic and argmax are executed unchanged. All 40 targeted tests pass.
Fresh full-model first-token simulation is the next gate; these regressions
are not full-model or board-inference acceptance.

## First exact full-model simulation token

At source commit `4d782f6`, the fresh full-model run in
`/tmp/tinystories-first-token-lmhead-20260909` selected token **11** at cycle
92,936,273. The harness subsequently started run 1, which is possible only
after run 0 reaches done, observes exactly one token commit, and checks both
the selected-token memory and public token output against 11. The second
reset run is still pending; this is not yet a two-run execution receipt.

Generated Futil SHA-256:
`e422c0093658d376e23510dea1a8375a87c0df10292d9a237454c862dc49fecc`.
Generated SV SHA-256:
`7e359dfd4ea1e78bdd141eeba52cc779d3698fb38b279def96e72a72188fc8b5`.
The static-image manifest self-hash is
`9016997551d6a963af0c24903eeb7a219b15cd50bcd8e0b82de050fa10346149`;
all 240 immutable image records and file hashes match the accepted baseline.
Fresh hardware elaboration has started in
`/tmp/tinystories-first-token-lmhead-static-20260909`, without reusing old
memory-mapping checkpoints. Programming remains gated on repeat simulation
and implementation checks. No first-token board acceptance or full timing
qualification is claimed.

### Repeat simulation passed

The same full-model process exited successfully after both reset runs. Each
selected token 11 at cycle 92,936,273, exposed 11 on the public token port,
and completed at cycle 92,936,279. The harness also checked that both cycle
counts and token results are identical. The successful execution receipt is
`/tmp/tinystories-first-token-lmhead-20260909/production-execution.json`, file
SHA-256 `a259f298b0c22868c24a2fc7fe27b31f6bf1233a9874bf8a94181a017f612622`.

An independent check authenticated the oracle fixture, compared its
`artifact_sha256` (not its JSON-file hash) to the receipt, checked the generated
Futil/SV hashes and memory-latency receipt self-hash, and verified both complete
event sequences from the log. The runner's existing `elapsed_seconds` field is
an absolute epoch timestamp, not elapsed runtime; do not use it as a latency
measurement. Reported cycle counts above are the measured simulation latency.

Fresh elaboration completed successfully. The mapper's inventory is 279
memories, identical to the previous elaboration; the staged downstream script
was corrected from a stale 266-checkpoint assumption to consume checkpoint 279.
Memory mapping is running. These two simulation resets do not count toward
the three required independent FPGA reconfigurations. All board acceptance
and the explicitly incomplete accelerator timing coverage remain outstanding.

## Final synthesis: correct simulation, excessive BRAM demand

The complete 279-memory mapping, native conversion, coarse/fine synthesis and
final netlist export all completed successfully. Final Yosys CHECK reports
zero problems. Nevertheless, the final design uses **1049 RAMB36E1 and 8
RAMB18E1**, exceeding the target's 955 full-block sites. No routing or
programming was attempted for this oversized netlist. Files are under
`/tmp/tinystories-first-token-lmhead-static-20260909/` (`initialized-final.json`,
`initialized-final.il`, `map-final.log`). The two exact simulation results
remain valid; synthesis completion is not board-fit acceptance.

Memory attribution from the mapped full design identifies 788 full blocks for
token weight codes, 64 for token scales, 64 for the two MLP weight matrices,
32 for Q/K/V/output weights, and 16 for GELU's LUT, plus other parameters and
scratch memories. The BRAM demand survives fine mapping and final optimization.
The next action is evidence-backed lossless on-chip memory allocation, not a
reduced model, changed arithmetic, DDR3, or an oversized route. As one concrete
measurement, the exact 50,257 token scales range from 14,525 to 105,952 and
therefore require only 17 unsigned bits, versus their current 32-bit storage.
Distributed-RAM capacity and allocation remain to be checked before selecting
a physical-memory change. No new RTL/memory-width repair has been made here.

## Lossless physical allocation candidate

The local xc7k480t tilegrid contains 27,150 SLICEM sites: 108,600
memory-capable LUTs, with 6,950,400 bits of raw 64-bit LUT storage. This is
an upper bound, not a placement guarantee. The two MLP code memories each
contain 131,072 eight-bit words; the four token-scale banks each contain
16,384 thirty-two-bit words. Together they hold 4,194,304 bits.

The checkpoint mapper now selects distributed RAM for these six immutable
memories, explicitly overriding their BRAM synthesis hints. It does not
change generated SV, model contents, widths, arithmetic, clocks, memory ports,
or the two-cycle register staging. The previous seven distributed scratch
memories retain their policy. The estimated reduction is 128 RAMB36s, from
1049 to 921 (plus the existing eight half-blocks); this estimate still requires
fresh synthesis and placement confirmation.

An executable regression first reproduced BRAM allocation under the old
policy. It now maps all six full-size candidate memory shapes to actual Yosys
LUTRAM cells, checks retained address/result register widths, and verifies an
ordinary token-code bank remains BRAM. All 41 targeted tests pass. The full
generated SV and its two passing simulation runs are unchanged; physical
implementation and board acceptance are not yet verified for this allocation.

### Capacity allocation synthesized; standard ABC avoids host OOM

All 279 revised memory mappings, native conversion and coarse/fine mapping
completed. Final ABC9 synthesis exited 137. The kernel log identifies Yosys as
the OOM victim, with 28,643,892 kB anonymous RSS; its log ends in ABC9_OPS after
expanding thousands of parameterized RAM64M behavioral models. This was a host
resource failure, not an inference mismatch.

A separate bounded final-mapping run from the saved fine netlist used Yosys's
standard ABC flow instead of ABC9. It completed successfully with zero CHECK
problems, without changing RTL, model contents, allocation, constraints or
router seed. The final report has 921 RAMB36E1, eight RAMB18E1, 24,688 RAM64M,
245 DSP48E1, four BUFG, one MMCME2_ADV and one BSCANE2. The raw BRAM and SLICEM
counts fit; legal placement is still required. RAM64M uses four 64-bit memory
LUTs per instance, so SLICEM pressure is substantially higher than the raw
model-bit estimate alone suggests.

The final JSON is
`/tmp/tinystories-first-token-capacity-static-20260909/initialized-final-abc.json`,
SHA-256 `8853f441b1aa8596969b38e1530e39bf7bd00a0615a74810ddda4b4c3deed79d`.
An independent comparison against `initialized-fine.il` verified all specified
native memory/MMCM/JTAG parameter bits across 25,619 instances, including
initialization and clock settings. No unspecified bits changed either; a
preliminary mismatch came from the checker's handling of compact RTLIL bit
representations and was resolved by width-aware comparison.

The fixed-seed route has started with seed 15, `--freq 30 --no-tmdriv`, the
unchanged XDC, router SHA-256
`fe6c462ee6336e3d2af467c97c57326b003e56f4371ef23a24a5c3502ee1a8e5`,
and partial device database SHA-256
`a96010ce1d1cfa0ac66bc52ba25ff0b77cccdf07d6835dd94eead9afab2d404e`.
The existing incomplete accelerator timing coverage remains explicit. Neither
routing nor board inference is claimed complete.

### Lossless memory-optimization probe during placement

While the unchanged placement process remained live, a separate bounded
diagnostic ran standard Yosys `opt_mem; opt_clean` on the original elaborated
RTLIL. It completed successfully and reduced declared memory storage from
34,515,136 to 32,640,160 bits (1,874,976 redundant bits removed). In particular,
all four token-scale banks changed from 32 to 17 bits; the memory optimizer
also narrowed several scale/gamma memories and removed the constant zero-bias
memory. This is a compiler optimization of redundant storage, not new
quantization or a modification to source tensors.

Artifacts are `/tmp/tinystories-capacity-optmem-probe.ys`, `.il`, and `.log`.
The current router input was not replaced, and no resource, timing or hardware
acceptance is inferred for this diagnostic. It is an evidence-backed fallback
if the high-SLICEM-pressure placement cannot complete within its existing
30-minute bound. Detailed live profiling was unavailable: current kernel perf
policy restricts it and noninteractive sudo requires a password. CPU accounting
confirmed the placer remained active; no kernel policy was changed.

The token-scale narrowing was additionally exercised in a bounded compiled
simulation: four original 32-bit ROMs loaded from the exact static images were
compared with their Yosys-optimized 17-bit counterparts. All 65,536 stored words
(including padded entries) matched at the same two-cycle output latency, with
unknown original outputs rejected. The Icarus run exited successfully with
`PASS all 65536 scale words, unchanged two-cycle output`. Diagnostic sources,
optimized RTL and executable use the prefix
`/tmp/tinystories-optmem-scale-check`. This checks the scale-memory transformation,
not complete optimized-model inference or placement; the active router input
remains unchanged.

### Separate lossless-width mapping candidate

The exhaustive scale-ROM comparison was rerun successfully before starting a
separate, bounded mapping of the optimized full-model RTLIL. Its input is
`/tmp/tinystories-capacity-optmem-probe.il`, SHA-256
`0cee3c605c6c488d2b579350a8cecf5adce9c0494141691e7635fc5d067a7ebb`.
It contains 278 memories after constant zero-bias elimination. The fresh
checkpoint directory is `/tmp/tinystories-first-token-optmem-map-20260909`;
the command uses `map_flattened_memory_checkpoints.py`, the production top,
a 120-second per-memory limit and a 1,800-second overall limit.

This is a separate candidate, not a restart or replacement of the live
high-SLICEM-pressure placement run. The original process was confirmed live
on the host after a sandbox-local process listing failed to show it. Neither
candidate has yet supplied a new routed bitstream or board inference result.
Generated model RTL, source tensor values, the 30 MHz clock, JTAG and router
seed remain unchanged. Full mapped-netlist equivalence is not established by
the scale-ROM test alone.

The separate mapping stopped after 47/278 memories: memory 48, token-scale
bank 0, had no valid distributed-RAM mapping. The helper returned process exit
zero despite its receipt correctly reporting `partial`; the receipt, not that
exit status, is authoritative. A direct replay with `debug memory_libmap`
identified every candidate rejection as `ROM mapping disabled (prune_rom set)`.
After `opt_mem` removes inactive write ports, the installed library explicitly
excludes the resulting ROM; this was not a 17-bit width or tensor-value error.

A private diagnostic copied the installed single-port LUTRAM template's
geometry, ports and initialization policy, omitting `prune_rom`. Mapping the
same failing memory then exited zero and extracted its data register. Files:
`/tmp/tinystories-rom-lutram-xc7.txt`,
`/tmp/tinystories-optmem-scale-map-rom.ys`, `.il`, and `.log`; the original
rejection is in `/tmp/tinystories-optmem-scale-map-repro.log`. This establishes
the mapping-policy cause only. The diagnostic has not been adopted into the
production mapper, and native mapped-ROM data/latency verification is still
required before doing so. The installed Yosys library was not modified.

### Native ROM verification and production mapping repair

The original high-pressure placement terminated with timeout exit 124 at its
1,800-second deadline, without completing a main placement iteration or
producing a routed result. This is a bounded implementation failure, not a
functional inference failure. Its artifacts and inputs are preserved.

A new executable regression first reproduced the ROM mapping rejection using
the production checkpoint helper. The helper now selects a repository-local
ROM-capable Series-7 LUTRAM template only for the six selected immutable
memories. The template retains the installed library's SP/DP/QP/SDP geometry,
cost, port and initialization definitions, omitting only `prune_rom`. Mutable
scratch memories retain the installed mapping library. The regression checks
native initialized-memory simulation, reset, read enable and two-cycle
staging; the existing writable-memory allocation checks also pass. All 42
targeted compiler, model, memory, CSR and host-checker tests passed.

Additionally, all four exact scale images were compiled through `opt_mem`,
the ROM-capable library and the installed native LUTRAM techmap. The result
contains 4,352 RAM256X1S instances. Icarus compared all 65,536 stored words
against the original 32-bit memories and passed with unchanged two-cycle
output. Artifacts use `/tmp/tinystories-optmem-scale-native-check` (`.ys`,
`.json`, `.v`, `.log`) and `/tmp/tinystories-optmem-scale-native-test`.
The test does not establish full-model post-mapping equivalence or timing.
No accelerator RTL, quantization, source images, clock or transport changed.

### Full optimized allocation completed

The fresh `/tmp/tinystories-first-token-rom-map-20260909` run completed all
278 memories, as confirmed by its `memory-checkpoints.json` receipt. Final
checkpoint `map-278.il` has SHA-256
`8328ed1d677fa988f83e2fe5620b304cfee490a4abde78e3adec80f7589e56c4`;
the ROM mapping template has SHA-256
`da3327c2fca40c3ac4fe824712086e93face871c36e5d3f1cf994c7449bb90f5`.
It retains eight small memories for the later `map_ffram`/`memory_map` stage,
including prompt/context storage and short constant tables. Allocation
completion therefore does not mean the final netlist is already native-only.

The next bounded stages run in
`/tmp/tinystories-first-token-rom-static-20260909`: native primitive conversion,
coarse preparation, fine mapping, and standard-ABC final mapping. Each is
limited to 900 seconds and subsequent stages start only after successful
exit. Native initialization/configuration comparison includes every `RAM*`
primitive type, DSP48E1, MMCME2_ADV and BSCANE2. Final counts, routing and board
inference remain pending. A read-only JTAG check again detected XC7K480T,
IDCODE `0x23751093`, via the specified HS3 programmer; no new image was loaded.

### Reduced-memory candidate passed final synthesis

Native conversion completed in 710.33 seconds, followed by coarse preparation
in 13.72 seconds, fine mapping in 94.08 seconds and standard-ABC final mapping
in 21.10 seconds. Final CHECK reported zero problems and no residual memories
or processes. The final design contains 830 RAMB36E1, 125 RAMB18E1, 12,544
RAM256X1S, 1,136 RAM64M and 163 DSP48E1, with four BUFG, one MMCME2_ADV and one
BSCANE2. These are capacity counts, not evidence of legal placement or timing.

The final JSON is
`/tmp/tinystories-first-token-rom-static-20260909/initialized-final-abc.json`,
SHA-256 `188110144cec0d7729462cdbabe8c5120cb9c39593c5d113ee167704a41773f3`.
Comparison against the fine checkpoint passed all 14,800 native memory, DSP,
clock and JTAG instances: all specified parameter bits matched and no
unspecified bits changed. The checker is `/tmp/verify-rom-native-params.py`.

A fresh 1,800-second place/route run uses the same router and partial device
database recorded above, unchanged XDC, `--freq 30 --seed 15 --no-tmdriv`.
Output prefix is `compiler-top-rom` in the same directory. The original
failed placement is preserved separately. No timing-coverage upgrade or
hardware inference success is implied by the successful synthesis.

### Backend-compatible packed ROMs

The reduced candidate's nextpnr run exited 255 during DRAM packing:
`Cannot pack unsupported primitive: RAM256X1S`. It did not reach placement.
Source inspection of this exact backend confirmed that single-bit SP RAM
primitives are rejected, whereas RAM32M and RAM64M are handled. This is an
explicit backend compatibility failure, not another timing or inference
failure.

The native-ROM regression was extended and failed on the actual RAM256X1S
output. The ROM library now retains only the installed SDP geometry, which
maps to supported packed RAM32M/RAM64M cells. The installed library and
nextpnr sources are unchanged. All 42 targeted regressions passed, including
native data/reset/enable/staging behavior and the supported-primitive check.

The exact four scale images now map to 5,804 RAM64M instances. A complete
fixture synthesis reported zero CHECK problems, and this nextpnr binary
passed its pack-only check with explicit per-port fixture I/O standards.
The production XDC was not changed. Artifacts have prefix
`/tmp/tinystories-packed-scale-pack-check`; synthesis log is
`/tmp/tinystories-packed-scale-pack-synth.log`.

The combined 120-second Icarus run timed out after native conversion and
simulation compilation; no exhaustive pass is attributed to that run. A
separate bounded Verilator build of the same exhaustive comparison completed,
and `/tmp/tinystories-packed-scale-verilated/Vtb` matched all 65,536 real scale
words with unchanged two-cycle output latency. Verilator is a two-state
simulation; the smaller Icarus regression separately exercises reset, enables,
known outputs and staging. The five-minute progress-instrumented Icarus
diagnostic is not needed to infer this Verilator result. These fixture passes
still do not prove full-model placement, timing or board inference.

The separately bounded, progress-instrumented Icarus diagnostic subsequently
completed with exit zero and matched all 65,536 words as well. Thus both the
four-state Icarus and two-state Verilator exhaustive comparisons passed for
the packed-ROM implementation. A fresh full-model mapping is running in
`/tmp/tinystories-first-token-packed-map-20260909`, with later stages prepared
in `/tmp/tinystories-first-token-packed-static-20260909`. Superseded ROM-map
intermediates 1 through 277 are being losslessly gzip-compressed; checkpoint
278, receipts, logs and source inputs remain uncompressed and preserved.
