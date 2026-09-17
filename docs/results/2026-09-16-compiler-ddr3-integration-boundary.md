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
leaving every other memory untouched. The pass also supports a deterministic
list of selected memories through indexed shared-port vectors. Three unit
tests pass, and applying it to the real Q/K/V weight tables (each 8-bit,
32,768 entries) parses and elaborates successfully through Yosys. The vectors
are the compiler-side boundary; a DDR3 arbiter still has to enforce one
outstanding request and map tensor names to the canonical full-image byte
ranges. This is deliberately not presented as full-model integration.

The shared transport primitive is now
`rtl/memory/llm_external_memory_arbiter.sv`. It accepts indexed compiler
requests, grants one owner at a time, converts the byte address to a 16-byte
Wishbone line, and routes the returned 64-bit lane to the owner. Its focused
Verilator test covers arbitration, line addressing, and upper-half response
extraction; it passes with `PASS`. Full-model integration still requires
instantiating this arbiter and supplying per-tensor base addresses from the
canonical image map.

The lowering now accepts per-memory base offsets and scales element indices to
byte addresses (`EXT_BASE_ADDR + index * (WIDTH/8)`). A Q/K/V rewrite using the
canonical offsets 565008, 451584, and 4099856 elaborated successfully through
Yosys. This closes the address-unit ambiguity; a full tensor-list rewrite and
simulation against the packed image remain outstanding.

The reproducible CLI for the complete transformation is:

```text
nix develop -c python scripts/analysis/externalize_compiler_memory.py \\
  --input result-compiler-top-30mhz-20260908/model-static-init.sv \\
  --manifest artifacts/diagnostics/tinystories-1m-ddr3-model-image-manifest.json \\
  --output /tmp/model-full-external.sv
```

It produces the 240-memory source with external initializers removed and
elaborates through Yosys. The first bounded exact-image simulation exposed a
protocol issue before any token result: generated `content_en` is level-held,
but the external cell re-issued a read after each response. This caused a
repeating response stream and the model never advanced. The external cell now
latches a `served` response until `content_en` is deasserted and holds `done`
at the native level semantics; the focused source-contract test covers these
rules. The rerun reaches millions of cycles with live memory traffic but does
not complete within the current five-million-cycle diagnostic bound, so the
next gate is a longer optimized run with a compact transaction trace and the
first-token checkpoint.

A four-thread exact-image run reached 60,000,000 cycles and 5,706,646 balanced
requests/responses before the 1,800-second wall limit, without `done`. This is
recorded in
`artifacts/diagnostics/2026-09-16-compiler-ddr3-first-token-simulation-60m.json`.
The remaining simulation risk is runtime to the known ~450-million-cycle
compiler datapath completion, not an observed DDR3 transport mismatch.

The loader-only PCIe/DDR3 baseline is independently accepted in
`artifacts/diagnostics/2026-09-16-ddr3-pcie-full-image-3-cold-starts.json`.
No accelerator integration or inference success is claimed here.

## Historical first-token result (not shared-DDR integration acceptance)

The initial long run used the clean-top source (`b030e34d…`), which is not the
accepted BRAM first-token accelerator. It returned settled token 0 and was
retained as a source-identity diagnostic. Repeating the same external-image
simulation with the accepted compiler-generated source
(`7e359dfd…`, Futil `e422c009…`) produced settled token 11 at cycle 92,936,288
(`643,641,072` memory requests). The receipt is
`artifacts/diagnostics/2026-09-16-compiler-ddr3-accepted-source-first-token-pass.json`.

The earlier claim that this closed the integration simulation gate is withdrawn.
The receipt records more memory requests than cycles and externalized RTL hash
`84397c4e…`, whereas the subsequent synthesis used `c18aff50…`. The original
harness has not been recovered. This evidence does not establish inference
through the actual shared single-port memory arbiter.

### 2026-09-17 integration audit and repairs

A delayed-response regression reproduced stale `done` on the synthesized
external-memory cell: after changing the requested address, `done` remained
asserted with the previous word before the new response arrived. The current
compiler externalization pass emits completion pulses, captures independently
timed operands at generated completion joins, and enables only the selected
token-weight bank. The shared arbiter uses hierarchical round-robin selection
and registered responses. Focused regressions cover streaming validity,
staggered completion, bank selection, arbitration, and persistent requesters;
these are not full-inference acceptance.

Separately, the compiler-enabled board shell disconnected PCIe loader writes
from DDR3. Integration-repository commit `e368449` restores transaction-level
host/accelerator ownership through the existing Wishbone owner mux. Its
enabled/disabled-shell tests check host writes and accelerator reads.

The replacement first-token simulation uses freshly transformed compiler RTL
SHA-256 `0d0546383070b515210ab989f0ebb2bc7e93e69895ada4df0e6b930fcf98cecb`,
the 240-port shared arbiter, and the packed model image
`e44d9bac0ddcf267cb2b41eb6f0aee623bacfb28809d9dffb7edc0319c43e593`.
It is bounded to 300 million cycles / three hours. At this audit it is still
running; no first-token result is claimed. Its Wishbone image model does not
simulate the physical PCIe endpoint or DDR3 PHY.

The board shell currently clocks the compiler adapter from the 83.33 MHz
rowstream domain, not its prior 30 MHz accelerator domain. The retired
placement reported 33.47 MHz rowstream and 53.02 MHz PCIe maximum frequencies,
below the unchanged 83.33/62.5 MHz requirements. Routing was stopped after the
functional defect was reproduced. No timing-qualified integrated bitstream or
hardware inference is established. Clock-domain restructuring, if required,
must preserve the validated PCIe and DDR3 clocks and be separately verified.

## Current source-closed integration boundary

`rtl/tinystories_1m_ddr3_backend.sv` now instantiates the externalized
compiler `main` and the shared 240-port arbiter. It preserves the generated
control/token ABI and presents a fixed 128-bit Wishbone read-only boundary,
which is the boundary used by the validated UberDDR3 loader. The wrapper does
not contain PCIe or DDR3 PHY logic; the physical top must connect its
`wb_*` signals without changing the accepted transport profile.

The wrapper contract tests pass, and pinned Yosys elaboration succeeds against
the actual accepted 240-memory externalized source. During this check Yosys
found a latch in the arbiter's shared loop-index variable at `PORTS=240`; the
loop indices are now process-local, with no protocol or timing-policy change.
The remaining implementation step is to add this source boundary to the
validated PCIe/UberDDR3 top and run the existing synthesis, placement, and
timing gates. The loader-only baseline remains unchanged.

`rtl/tinystories_1m_ddr3_command_adapter.sv` supplies the corresponding
control splice: it accepts the existing PCIe-side prompt-token stream,
assembles four prompt words, holds `start` and `valid` until generated `main`
asserts `done`, and presents the resulting token with a ready/valid handshake.
It also forwards the wrapper's Wishbone signals and counts accepted memory
requests. Its contract tests and a pinned Yosys elaboration pass with the
240-port backend. This is intentionally a transport-facing adapter only; it
does not replace the physical PCIe/UberDDR3 top or claim board operation.
