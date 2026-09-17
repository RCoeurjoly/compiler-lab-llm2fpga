# Shared-DDR3 first-token simulation: preserved harness

This is a source snapshot of the run launched on 2026-09-17, **not a passing
inference receipt**. `qualification-audit.json` records the audit at launch;
its `running` field is historical, not a live process indicator.

`driver.cpp` and `wrapper.sv` are byte-identical to the running harness:

- driver SHA-256: `a0b7b1e1d667de665ab606a0a1b71c380118c2310f88af7f11b40b3e3ebe8dc3`
- wrapper SHA-256: `d9818ffaa6aaa008b57c930273034f40b83aebec4b5ea5e4c39264df86003161`

The compiled accelerator is produced by `scripts/analysis/externalize_compiler_memory.py`
from the accepted compiler-generated source; its identity and packed-image
identity are recorded in the audit. Compiler-pass and arbiter changes are
committed in `ee16dc9`. No kev-gpt accelerator RTL is used.

The wrapper contains the original absolute `$readmemh` path intentionally, to
preserve the exact harness identity. Reproduction elsewhere requires replacing
only that path with the same image's 128-bit-line hex file and recording the
new wrapper hash. This snapshot is not a portable build target yet.

The original Verilator invocation (inside `nix develop .#default`) was:

```sh
verilator --cc --exe --build --timing -j 4 -O3 -Wno-fatal \
  --top-module compiler_ddr3_cpp_wrapper \
  --Mdir /tmp/compiler-ddr3-current.2Z9Mo4/obj-current-pass -CFLAGS -O3 \
  /tmp/compiler-ddr3-current.2Z9Mo4/current-pass.sv \
  /nix/store/xs26iaazqfp72wr0fcnkn73krld2ln6d-llm_external_memory_arbiter.sv \
  /tmp/compiler-ddr3-current.2Z9Mo4/sim/compiler_ddr3_cpp_wrapper.sv \
  /tmp/compiler-ddr3-current.2Z9Mo4/routed_source_main.cpp
timeout --signal=TERM --kill-after=10s 10800s \
  /tmp/compiler-ddr3-current.2Z9Mo4/obj-current-pass/Vcompiler_ddr3_cpp_wrapper 300000000
```

The driver supplies frozen prompt IDs `[7454, 2402, 257, 640]`, requires token
`11` at `done`, and checks single-outstanding request/response accounting.
The wrapper exercises the actual 240-port arbiter against a preloaded,
fixed-latency Wishbone memory model. It does **not** exercise PCIe loading,
owner-mux arbitration, DDR3 calibration/PHY, asynchronous clock crossings, or
physical timing. Counts are diagnostics, not an ordered address/data trace.
The model does not explicitly reject out-of-range addresses. A passing result
must therefore retain these scope limits; integrated board acceptance remains
a separate requirement.

## Terminal result and localized correction

The original run finished with **FAIL**, not a timeout: 145,253,465 cycles,
13,100,528 requests and responses, token **640**, expected **11**. Its terminal
log SHA-256 is `1db4ee1f5b5579abda8d2a7c041768fc075cebd115fa23e2f9ffe2468d63c140`.
Do not use its synthesized candidate for hardware acceptance.

Checkpoint replay against the compiler-generated BRAM implementation, initialized
from the same hash-verified image, matched block inputs, layer normalization,
Q/K/V projections, and all 1,600 captured attention-score writes. The earliest
observed mismatch was attention exponential write ordinal 1,040, address 128:
expected `0x0ebd69`, actual `0x0ff008`. These are LUT entries 4075 and 4095.

An observational driver linked against the unchanged failing simulation library
recorded this sequence (before each active clock edge):

| Cycle | Static phase | Read enabled | Requested index | Response index | Pending | Read data |
|---|---|---|---|---|---|---|
| 2458836 | 0 | 1 | 4095 (previous) | 4095 | 0 | ff008 |
| 2458837 | 1 | 1 | 4075 | 4095 | 1 | ff008 |
| 2458838 | 2, consume | 0 | 4075 | 4095 | 1 | ff008 |

Thus consumption precedes completion of the correct lookup. The externalization
pass handled dynamic completion groups, but had retained BRAM-latency static
schedules for attention, GELU, and the fallback prompt memory.

`legalize_static_external_reads` now holds the shared static scheduler at the
last read phase until the corresponding response arrives. It preserves memory
addressing, arithmetic, and transport. The three recognized schedules were
audited for side effects at the held phases; unfamiliar schedules are rejected.
This is an exact-TinyStories schedule legalization, not a general Calyx static
control conversion.

The new RTL regression failed before the change for all three schedules and
passes with response delays of 1, 7, and 19 cycles. It covers both GELU reads,
repeated operations, request counts/addresses, and a disabled conditional prompt
read. The focused external-memory suite passes 12 tests.

The candidate is generated from the same raw compiler source. Disabling only
the new legalization reproduces the previous `0d054638...` source hash exactly.
With the correction, the source SHA-256 is
`b93f285e8ae877b110774c27b8ab1d4a7c0b37d277be75d5e8142d9fc739ae9d`.
Full-model checkpoint replay, first-token acceptance, new synthesis/timing, and
hardware acceptance remain pending for this candidate. No PCIe, DDR3, clock, or
constraint changes accompany this correction.

### Completed bounded replay

The corrected model completed a five-million-cycle capture. All **9,344**
captured writes through attention output/residual and the second layer
normalization match the compiler BRAM reference. This includes all 1,600
attention exponential writes that previously diverged. MLP/GELU writes were
not reached in this capture; this is not full first-token acceptance.
`static-wait-checkpoints.json` records counts, hashes, and the separate full-run
launch. The additional contract tests bring the focused passing total to 16.
