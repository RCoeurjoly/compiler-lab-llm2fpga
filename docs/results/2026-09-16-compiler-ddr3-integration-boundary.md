# Compiler RTL to DDR3 integration boundary

The authenticated compiler output is
`result-compiler-top-30mhz-20260908/model.sv`. Its top-level `main` interface
has control and token ports (`start`, `valid`, four prompt words,
`token_index`, `done`, and `token_id`) plus `clk`/`reset`; it has no external
memory request or response ports. The model therefore cannot be connected to
the validated PCIe-to-UberDDR3 loader by top-level wiring alone.

The generated `main` instantiates 294 logical memories: 280
`seq_mem_d1_bram`, eight `seq_mem_d1_lutram`, 14 plain `seq_mem_d1`, and one
each of `seq_mem_d2`, `seq_mem_d3`, and `seq_mem_d4` (the latter are wrappers
around flattened memories). Immutable tensor images are initialized by
`model-static-init.sv` using 240 image files. Runtime activations and state
must remain local; only immutable tensor memories are eligible for DDR3.

This establishes the actual integration blocker and prevents an invalid claim
that the loader-only bitstream contains the compiler accelerator. The required
next implementation is a compiler-owned memory lowering boundary (or an
equivalent out-of-tree Yosys transformation) that replaces eligible immutable
memory cells with a shared, ordered 128-bit DDR3 request/response port while
preserving each memory's logical read latency and data width. The transformation
must emit the existing full-image address map and retain a BRAM mode for
equivalence testing.

The initial shared contract is defined by
`scripts/analysis/compiler_external_memory_contract.py`; its canonical hash is
`b5815f8488ab9dce79c774106d1024514b1d3afd4bcdda4351de402301b9f4bd`. It is
byte-addressed, uses 16-byte lines, permits one outstanding request, and
requires in-order responses. Its three contract tests pass under the Nix
Python environment; this is a protocol foundation, not yet a full-model
lowering.

The first source-level slice is implemented by
`scripts/analysis/externalize_compiler_memory.py`. It replaces one selected
`seq_mem_d1_bram`/`seq_mem_d1_lutram` instance with a latency-aware
`seq_mem_d1_external` cell and exposes request/response ports on `main`, while
leaving every other memory untouched. Two unit tests pass, and applying it to
the real `q_weight_codes_i8` instance (8-bit, 32,768 entries) parses and
elaborates successfully through Yosys. This is deliberately not presented as
full-model integration: the next step is a shared arbiter and placement map
for all eligible immutable memories.

The loader-only PCIe/DDR3 baseline is independently accepted in
`artifacts/diagnostics/2026-09-16-ddr3-pcie-full-image-3-cold-starts.json`.
No accelerator integration or inference success is claimed here.
