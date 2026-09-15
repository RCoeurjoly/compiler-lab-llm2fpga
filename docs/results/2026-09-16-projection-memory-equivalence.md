# TinyStories-1M projection BRAM/DDR3 equivalence

Status: single-table contract gate passed (simulation/reference model and
synthesis shell). Full-model DDR3 integration and board inference remain
deferred.

The table is the exact compiler image
`result-compiler-top-30mhz-20260908/image-q_weight_codes_i8.hex`, restricted to
the 4096 INT8 words for `blocks.0.attn.q.weight`. Its source SHA-256 is
`1fc141206dcc2be0e32f20da7d698a756b2898908ff505d65d7f206f50fc5932`; the
selected image hash is `4471722eea1e140618812aaef4e60f5ba081b3f720ef79c81fb28c5f415a3395`.

The executable model in
`scripts/analysis/memory_placement_equivalence.py` implements the compiler
logical byte-address contract, one-cycle synchronous BRAM, and a single-
outstanding 128-bit DDR3 adapter with 16-byte lines and eight-line sequential
prefetch. Both backends replayed 260 addresses covering row starts, line
boundaries, repeated reads, and the last word. Ordered response hash was
`ec163abf77287fc11d17974ab5f2e2323ae2cef1df3091b35286fd2acf3e58` in both
modes. The signed-64-bit wrapping GEMV output hash was
`ef3ee7766812f746d8cb1330008d34e7f50c3544e4dee2d9e49e6a3c1d3c545f` in both
modes; no mismatch was found. DDR3 required two external line requests and
258 cache hits for this trace.

An exhaustive replay then covered all 4096 table words plus every 16-byte line
boundary (4354 requests). It also passed with no mismatch; the DDR3 model used
32 external line requests. Its receipt is
`artifacts/diagnostics/tinystories-1m-q-projection-memory-equivalence-exhaustive.json`.

Modes are selected through the canonical placement records emitted by
`scripts/analysis/write_memory_placement_manifest.py`; the BRAM and DDR3
manifests are recorded at
`artifacts/diagnostics/tinystories-1m-q-placement-bram.json` and
`artifacts/diagnostics/tinystories-1m-q-placement-ddr3.json` respectively.

Commands:

```text
nix develop -c python scripts/analysis/memory_placement_equivalence.py \
  --image result-compiler-top-30mhz-20260908/image-q_weight_codes_i8.hex \
  --output artifacts/diagnostics/tinystories-1m-q-projection-memory-equivalence.json
nix develop -c yosys -s scripts/analysis/synthesize_memory_placement_shell.ys
```

Yosys 0.66 synthesized `rtl/memory/llm_ddr3_adapter_shell.sv` to 25 cells in
the adapter (six enabled state registers, mux/compare/shift logic), with no
memories or unresolved submodules. The structural receipt is
`artifacts/diagnostics/llm-ddr3-adapter-shell-yosys.json`.

The same shell passed a Verilator reset/two-read handshake test; its receipt is
`artifacts/diagnostics/llm-ddr3-adapter-sim.json`.

The adapter's 128-bit/16-byte address and lane mapping is statically bound to
the measured two-lane UberDDR3 source/profile in
`artifacts/diagnostics/tinystories-1m-q-uberddr3-binding.json`.

An initial Yosys STA invocation is recorded in
`artifacts/diagnostics/llm-ddr3-adapter-shell-sta.json`. It reports no timing
paths because the shell has not undergone Kintex-7 technology mapping; this is
explicitly not timing closure.

This is not yet evidence that the physical UberDDR3 controller, full weight
image loader, timing closure, or hardware inference works. The next gate is to
connect this contract to the validated UberDDR3 user port and repeat the same
single-table readback equivalence against its actual memory model.
