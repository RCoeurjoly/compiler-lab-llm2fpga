# Loaded-image ownership-mux simulation

This is test-only RTL/C++, not accelerator implementation RTL. The production
candidate and active routing experiment remain unchanged.

The host driver writes all 4,136,720 image bytes through the pinned production
ownership mux, reads every word back and compares with the input file, then
supplies the frozen four-token prompt. The memory model starts without
`readmemh` initialization. It inserts periodic request stalls and delayed
responses. The expected inference result remains token 11; a successful load
alone is not inference acceptance.

The corrupt-write negative control returned 2 at line 17, word 0, as expected.
The clean load-only run returned 0. Full first-token inference also returned
0: token 11, 165,186,630 cycles and 13,116,912 requests/responses. See
`result.json` and the complete `run.log`; `launch.json` preserves the earlier
launch-time state. This takes 95,632 more cycles than the previous preloaded
direct-Wishbone model and issues the same number of accelerator reads.
All test doubles remain below the production
Wishbone ownership boundary; PCIe and DDR3 physical interfaces are not modeled.

Reproduce from the repository root using the unchanged payload-reset model:

```sh
nix develop .#default -c timeout --signal=TERM --kill-after=10s 1800 \
  verilator --cc --exe --build --timing -j 2 -O3 -Wno-fatal \
  --top-module command_integration_wrapper \
  --Mdir /tmp/compiler-ddr3-owner-sim.lXS9X3/obj \
  /tmp/compiler-ddr3-payload-reset.tywJVR/model.sv \
  /nix/store/9zbn7rgdgpw2q7h92sj22h3m4b446d5a-llm_external_memory_arbiter.sv \
  /nix/store/4n5p2q9c3im9qrizysw6jcfc4ni0xc39-tinystories_1m_ddr3_backend.sv \
  /nix/store/dn9gwzarhz2kdlc9z8v7h7s6q1fpz7qr-tinystories_1m_ddr3_command_adapter.sv \
  /nix/store/5f2fppa4a3636py498f4pv5500dsizfm-task6_wishbone_owner_mux.sv \
  "$PWD/artifacts/diagnostics/2026-09-18-owner-mux-simulation/owner-integration-wrapper.sv" \
  "$PWD/artifacts/diagnostics/2026-09-18-owner-mux-simulation/owner-integration-driver.cpp"

timeout --signal=TERM --kill-after=10s 10800 \
  /tmp/compiler-ddr3-owner-sim.lXS9X3/obj/Vcommand_integration_wrapper \
  +MODEL_BIN=/tmp/compiler-ddr3-current.2Z9Mo4/image.bin
```

Use `--load-only` to stop after readback and `--load-only --corrupt-write`
for the negative control (expected exit 2). The build and run directories are
temporary; sources and the measured load/inference results are tracked here. Candidate
regeneration and image provenance are documented in the payload-reset report
and the model-image manifest. Never substitute another source merely because
it has the same filename; check the receipt hashes.

## Ordered trace reference

`trace-result.json` records a second passing run with the test-only observer
from `sim/compiler_ddr3/reference_memory_trace.sv` and its bind file. Build
with those two additional sources and a fresh `--Mdir`; run with
`+TRACE_FILE=/path/to/reference.trace`. The completed run produced the same
token, cycle count and transaction totals, and a byte-identical `run.log`.
Neither compiler RTL nor the baseline wrapper/driver was changed.

The trace has 13,116,912 ordered request/response pairs. Every response was
also checked against the authenticated image: multiply the 128-bit line
address by 16 and interpret the image's 16 bytes as a little-endian integer.
All matched. The raw 935,312,356-byte trace remains in the receipt's scratch
directory rather than Git. Its SHA-256 is recorded for subsequent comparison;
it can be regenerated using the unchanged sources and the observer.

The validation used `records()` from
`scripts/analysis/compare_memory_traces.py` to check syntax, sequence, retained
response address and balanced completion, followed by a per-response image
comparison and an assertion of exactly 13,116,912 responses. This is a
reference trace, not evidence that the physical DDR3 simulation has passed.

## Authenticated streamed replay package

`artifacts/reference/tinystories-1m-compiler-ddr3-trace-replay.json` is the
compact receipt for the exact hardware replay input. It binds the frozen
candidate `daed4badbce39933ffbbec461fa40603ddfdec0d137f543132fd02fd7ec1d88a`,
the authenticated image
`e44d9bac0ddcf267cb2b41eb6f0aee623bacfb28809d9dffb7edc0319c43e593`, prompt
`[7454,2402,257,640]`, token `11`, and source trace
`e61bb6100af2c612f3cbd3beef0f4fff0dce3194f1590fca0cee9d0f7ed2df23`.
Its 13,116,912 replay records are 20-byte little-endian address/response
tuples; the 262,338,240-byte binary is deliberately retained only at the
hashed scratch-artifact path recorded by that receipt, not in Git.

Create it with `scripts/analysis/build_compiler_trace_replay.py`. The converter
parses and hashes one Q/R pair at a time, fsyncs a sibling temporary binary,
then independently stream-compares every generated record with the complete
authenticated trace before atomically replacing its destination. A malformed,
truncated, reordered, duplicate, trailing, or hash-mismatched trace cannot
replace an existing package. The comparison copies observed response bytes; it
does not claim that every runtime response can be reconstructed solely from the
immutable image bytes. The image receipt/hash binds the package to the loaded
image, while the source trace remains the authority for all response data.
