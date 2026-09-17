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
