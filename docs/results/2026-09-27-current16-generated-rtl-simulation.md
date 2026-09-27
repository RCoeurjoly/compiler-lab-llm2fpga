# Compiler-generated TinyStories-1M sixteen-token simulation checkpoint

Status: **exact generated-RTL token/context/output simulation, not full Task 4
acceptance or board inference**. This checkpoint preserves the current-source
sixteen-token result from the bounded Nix-backed run as tracked artifacts in
`artifacts/diagnostics/2026-09-27-tinystories-current16-rtl/`. No kev-gpt RTL
is included.

The tracked directory contains the generated Calyx `model.futil`, its generated
SystemVerilog `model.sv`, the ordered simulator event stream
`production-execution.jsonl`, and its provenance-bound
`production-execution.json` receipt. Their SHA-256 values are, respectively:

```text
13f2a5f8de4e82fdedbd306e2c4c28c8d7932a92b365752c30e684a42d6ec974  model.futil
938fe8a1cd2508178c98719e3c403d90323f58b146481fe808568ce3a67e8e91  model.sv
23e3d80de8ee4961fa0189b216fae55d91db1a420a5542cbb9af4cf5ae1c8c76  production-execution.jsonl
1de74a60914783c4cd7cce8a1c620269751a8aed7ae863a81eca68239114cbf1  production-execution.json
```

A fresh Nix-Python audit checked those files against one another and the
tracked authenticated continuation fixture. Both independent reset/start
runs selected and publicly returned exactly
`[11,612,373,257,1310,2576,3706,20037,13,1375,6151,284,711,2354,287,262]`.
The ordered stream has 32 selected-token events, 32 output-port events, two
completion events, and no context-mismatch event. Each run completed after
1,972,293,279 simulated cycles. The original run exited zero after 17,355.28
wall seconds. The receipt binds the event log, Futil, SV, source memories and
the legacy model-oracle identity; the continuation fixture binds that legacy
identity to the frozen sixteen-token contexts and tokens.

Verification after promotion: the four tracked files matched their raw
counterparts byte-for-byte; a fresh Nix-Python audit checked all 89 local
source-image hashes against the receipt and the event ordering/counts above.
The Nix `unittest` runner passed 33 production-harness, model-production, and
memory-latency tests. Including the separate sixteen-production test file
yielded 34 passes and one pre-existing error: its geometry assertion expects
`gelu_output_q16_16` as a separate memory, while the current compiler aliases
that buffer to `c_fc_output_q16_16`. This is not a green repository-wide test
claim; the stale assertion still needs an evidence-backed update.

The simulator was run with source tensors independently checked byte-for-byte
against the Nix-pinned package
`/nix/store/rmbfgi87w4b7g2kz2kz4rwqy9dfn076m-kev-gpt-source/model_packages/tinystories-1m`
and HF snapshot
`/nix/store/kw3s159yv90pk879nm0f7v4ikkrxz83w-tinystories-1m-hf-snapshot`
(89 source memories, zero mismatches). The current production runner still
defaults to an ambient home-directory model/package path and does not expose
those Nix inputs as CLI arguments. Thus the tracked result is durable and
Nix-verified, but a self-contained Nix **reproduction command** is not yet
established. Do not treat this checkpoint as closing that reproducibility
requirement. The long run also recorded token/context/output events rather
than internal activation-checkpoint hashes; that separate Task 4 requirement
remains open.

## Nix-pinned regeneration preflight

A fresh `nix develop . -c python` check bypassed the runner's ambient default
paths by passing the package and HF snapshot above directly to the existing
`load_successor_exact_model` API. The current compiler regenerated Futil
SHA-256 `13f2a5f8de4e82fdedbd306e2c4c28c8d7932a92b365752c30e684a42d6ec974`
and all 89 source-memory byte hashes in the tracked receipt. The initial
sandboxed command could not update Nix's fetcher cache; the identical check
with normal Nix access exited zero. No model input was downloaded or replaced
by the Python check; it read the existing Nix-store package and snapshot.

`nix build --no-link --print-out-paths .#calyx` resolved pinned Calyx 0.7.1
at `/nix/store/80r0hfh3w0w1y2vssxr70h91g33gi9dg-calyx-0.7.1`. Running
the existing production latency-library overlay and Calyx flags on the
tracked Futil, then the unchanged memory-annotation function, regenerated
the exact tracked SV hash
`938fe8a1cd2508178c98719e3c403d90323f58b146481fe808568ce3a67e8e91`.
The overlay receipt SHA-256 was
`e6be59542728c10dc1b6c41fa701a130aa4ae4e7c3eaac6a6ef6932fa9440293`.
The current harness generator also reproduced the recorded C++ harness hash
`6e09fe97edb1751af5e220a2713af2ec6a63080ffc17a7ac18df3feb492f052a`.
These checks localize the remaining replay gap to runner orchestration and the
long Verilator execution, not model loading or Calyx code generation. They do
not substitute for an end-to-end Nix replay of the simulator.

Nothing here proves resource fit, full timing coverage, a bitstream, a JTAG
transaction, or board inference. The accepted first-token board image is
unchanged. The current physical blocker is the two-token JTAG CSR response
alignment, after a legal two-token route and bitstream, as documented in
`2026-09-27-tinystories-two-token-synthesis-route.md`.

## Full-sixteen pre-DSP synthesis checkpoint

While a fresh Nix-pinned two-run simulator replay was still live, the existing
`--preserve-multipliers` frontend was run on the same authenticated full-16
static-init generated SV (normalized SHA-256
`ceec2a666d1e7d013c51acbafeeef275f7de71fc623ac2724b6bc25440062415`).
It exited zero under a 12 GiB virtual-memory cap and produced pre-DSP RTLIL
SHA-256 `ccc02961764ce1a1f789127497e927d47645ab3c86ce1da70ff7b7bdbb6312ed`
with 39 `$mul` cells. The pinned Yosys 0.66 `synth_xilinx -family xc7
-top main -run map_dsp:coarse` stage, with the existing
`xilinx_dsp.multonly=1` setting, exited zero and inferred 225 `DSP48E1`
cells. Its RTLIL and log SHA-256 values are respectively
`3305182733b6b726f5f3d2f11d6f5d72691d53ca9c51c3c20ede5559f3be3a32`
and `bc0fe7d190e4aa6bcfc09e96ea6281325f39d7a65acfd8cdf0bc8005e0f14912`.
The checkpoints are under the ignored
`.superpowers/sdd/2026-09-09-tinystories-16-token-board/current16/static-image/`
working directory. They contain the compiler-generated core, not a finalized
CSR-integrated board image. No full-16 native memory mapping, placement,
routing, timing qualification, bitstream, or board inference follows from this
DSP checkpoint.

The existing YPCB clock, JTAG CSR, and BRAM top were then elaborated against
that DSP-mapped full-16 core with `TOKEN_INDEX_WIDTH=4` (the core's generated
`token_index` input is four bits). Bounded Yosys hierarchy checking exited
zero, derived the CSR with the same width, and reported no token-index port
width warning. Its log SHA-256 is
`c3f27a92d8fb7f5e85c14a18f15f1c31d47be84b8748edc875f7c80fced6b353`.
The 109 coarse memories and 225 DSP48E1 cells are pre-mapping hierarchy
counts, not FPGA utilization. The wrapper still contains the unresolved
physical CSR response shift; successful elaboration is not a functional board
gate or an endorsement of that response path.

The compiler's runtime BRAM bank plans for the exact two-token and sixteen-token
artifacts differ by 2,174,976 physical capacity bits, or 59 RAMB36-equivalent
banks, as row capacity grows from 8 to 20. The routed two-token implementation
uses 755 of the target's 955 RAMB36E1 sites, leaving a nominal 200-site margin.
This comparison does **not** establish sixteen-token fit: the bank plan is not
post-map utilization, and packing, LUTRAM use, placement, routing, and timing
must still be checked on a complete sixteen-token board netlist. It does show
that the added context capacity alone does not exceed the presently unused
raw RAMB36 site count.

## Full-sixteen YPCB synthesis and pack checkpoint

The exact authenticated full-sixteen compiler-generated core was integrated
with the existing YPCB clock, BRAM top, and JTAG CSR at
`TOKEN_INDEX_WIDTH=4`, then run through the same pinned Yosys 0.66 native
memory and DSP mapping flow used for the two-token candidate. The
restartable mapper completed all 108 memories. A 600-second native BRAM
mapping attempt reached 744 template expansions but timed out; one bounded
900-second retry of the identical input and policy completed. The native
memory RTLIL SHA-256 is
`9e7703977a0fab370a19577d1fab3fdabf19e7fb473a8b77623f2bb1689df190`.
The final Yosys `check` found zero problems and no residual memories. The
final JSON and RTLIL SHA-256 values are, respectively,
`4e0de71853fef401d8d78a3eac21e4979ce47c9abaa84368af2fb0ed50f68bb2`
and `ed1ae857926784924f06972ff9d62d2a5cfba6df14de2b8cb28ac4517ca5abe3`.

The production-pinned nextpnr-xilinx pack-only gate exited zero with the
unchanged YPCB XDC, seed 15, 30 MHz target, and `--no-tmdriv`. Its log
SHA-256 is
`e88f58c6d51eedabeecd1c907c316058e8514e4cb6917fe9d07cd28ccb67371d`.
Pack reported 169,372/597,200 SLICE_LUTX (28%), 755/955 RAMB36E1
(79%), 89/1,910 RAMB18E1 (4%), 190/1,920 DSP48E1 (9%), one BSCAN,
and one MMCME2_ADV. These are packed resource counts, not placed or routed
timing results. The native mapped image and pack log are retained in the
ignored `current16/static-image/` plan workspace; the hashes above identify
the exact checkpoints.

This demonstrates that the complete full-sixteen board netlist passes
synthesis and resource packing without exceeding device capacity. Placement,
routing, covered-path timing, bitstream generation, physical CSR response
alignment, and board inference remain unproved. In particular, pack success
does not close the existing two-token CSR failure or BRAM/DSP timing coverage.
