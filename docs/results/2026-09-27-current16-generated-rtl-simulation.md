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
unchanged. The immediate physical blocker remains the two-token route
documented in `2026-09-27-tinystories-two-token-synthesis-route.md`.
