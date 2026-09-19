# Compiler TinyStories-1M fast DDR3 integration

## Decision and destination

Achieve authenticated TinyStories-1M first-token inference on YPCB using the
compiler-generated accelerator, the proven PCIe transport, and production
UberDDR3. Preserve the exact model image and arithmetic, two DDR3 byte lanes,
333/83.33 MHz DDR/controller clocks, timing constraints, and board interfaces.
Kev-gpt may remain a behavioral reference but none of its accelerator RTL is
an implementation input.

Exhaustive pin-level simulation through the Micron model is no longer an
acceptance gate. The production-profile XSim run started on 2026-09-18 was
terminated after 24 hours 29 minutes at 177,400,000 testbench cycles. It had
completed sequential write/read sweeps without an error but reached only
14,489,554 of 33,554,432 addresses (43.2%) in random-write BIST; random-read,
alternating write/read, model loading, and inference had not begun. The logs
were retained in `/tmp/compiler-micron-full.nIto9M` as local diagnostic
evidence. Continuing this gate would make iteration depend on days of
repetitive memory-model execution and still would not cover PCIe or prove the
integrated bitstream on hardware.

Physical DDR3 correctness is therefore established on YPCB. Transaction-level
simulation establishes compiler and memory-protocol semantics. A temporary
exact-trace hardware checkpoint separates transport/DDR3 integration failures
from accelerator computation failures before paying for repeated full
accelerator builds.

## Frozen implementation boundary

Retain the payload-reset compiler candidate and authenticated 4,136,720-byte
image identified by
`artifacts/diagnostics/2026-09-18-owner-mux-simulation/result.json`. The
production deliverable contains compiler-generated accelerator RTL, the
existing command adapter and owner mux, the validated PCIe transport, and the
pinned UberDDR3 controller/PHY. It retains:

- two byte lanes with x16 data;
- 12,000/3,000 ps controller/DDR periods;
- 15/10/3 row/column/bank widths and 25-bit burst Wishbone addresses;
- 128-bit Wishbone data and 16 byte enables;
- `SDRAM_CAPACITY=4`, `SPEED_BIN=1`, `ODELAY_SUPPORTED=0`, and `DLL_OFF=0`;
- production `BIST_MODE=2`, `BIST_TEST_DATAMASK=0`, `ECC_ENABLE=0`, and
  `SECOND_WISHBONE=0`;
- the existing clocks, XDC constraints, fixed nextpnr strategy, and PCIe
  lifecycle protocol.

The diagnostic trace replayer is temporary test RTL. It must not replace,
modify, or become an input to the compiler-generated accelerator. The trace is
derived from the authenticated passing compiler simulation rather than from
arbitrary synthetic traffic.

## Fast semantic gate

Use the transaction-level external-memory harness to test the current
compiler-generated implementation before synthesis:

1. Load every authenticated image byte through the host-side memory interface
   and read back the complete image exactly.
2. Supply prompt tokens `[7454,2402,257,640]` and require first token `11`.
3. Require balanced, ordered requests and responses, stable requests under
   backpressure, legal addresses and byte enables, and no unknown response
   data.
4. Emit a canonical ordered `(address, response-data)` trace plus hashes that
   bind the trace to the model image, compiler RTL, prompt, and expected token.
5. Demonstrate negative controls for image corruption, response corruption,
   and timeout.

This gate validates accelerator semantics and the external-memory protocol. It
does **not** validate PCIe TLP ingress, PCIe reset/clock crossings, UberDDR3
calibration or PHY behavior, physical DDR3, placement, routing, or board
timing. Results must state those exclusions explicitly.

## Hardware localization ladder

Each bitstream is tested through the established automated programming and
deferred-authorization PCIe lifecycle protocol. Stop at the first failing gate
and retain its diagnostics; do not apply speculative accelerator fixes.

1. **Loader baseline:** require production UberDDR3 initialization,
   calibration, and BIST; enumerate the validated PCIe endpoint; load the
   complete image; and verify complete readback against the authenticated
   image.
2. **Exact trace replay:** build a temporary diagnostic image around the same
   production PCIe/UberDDR3 shell. Replay the canonical first-token request
   sequence and compare every returned response in order. Expose persistent
   CSRs for calibration/BIST state, replay state, accepted request/response
   counts, first mismatching index/address/expected/actual data, and terminal
   error status.
3. **Full accelerator:** replace only the trace replayer with the unchanged
   compiler-generated accelerator. Reload and verify the complete image, send
   the authenticated prompt, and require first token `11` with balanced
   request/response diagnostics.

A trace-replay failure localizes the defect to the PCIe/load/DDR3 integration
or its request boundary. A passing trace replay followed by accelerator failure
localizes it after that boundary, in accelerator control, arithmetic, or the
full accelerator's physical integration. Successful synthesis, routing, or
timing reports alone do not satisfy any hardware gate.

## Consolidation ordering

Do not implement the approved 197-bank request-controller consolidation until
the current compiler implementation passes the semantic, loader, trace-replay,
and full-accelerator first-token gates. Then apply the compiler-owned
consolidation described by
`2026-09-18-compiler-ddr3-bank-consolidation-design.md` and repeat every gate.
The image, memory ABI, transport shell, clocks, DDR3 profile, and expected token
remain unchanged; only latency and resource use may change.

## Iteration and evidence policy

- Run semantic and boundary diagnostics before synthesis.
- Reuse authenticated immutable artifacts and avoid rebuilding unchanged
  stages, while requiring a clean final reproduction.
- Automate bitstream programming, PCIe recovery, loading, readback, test
  execution, and receipt collection.
- Every hardware failure must preserve the first mismatch and counters needed
  to choose the next boundary; a new bitstream requires evidence from the
  preceding gate.
- Preserve loader-only and passing compiler baselines and record source,
  bitstream, image, trace, tool, timing, and result hashes.
- Keep unresolved nextpnr cell-timing coverage explicit. Functional hardware
  success does not convert uncovered paths into timing qualification.
- Micron-model simulation remains available only for a focused diagnostic
  question. It is not a prerequisite for synthesis or board testing and must
  not be used to claim PCIe or hardware success.
- First-token success does not establish autonomous multi-token inference.

## Acceptance

The current implementation passes only when the transaction-level full-image
and first-token gate, production hardware loader/readback gate, exact-trace
hardware gate, and unchanged full-accelerator first-token gate all pass with
authenticated receipts. The consolidated implementation must subsequently
pass the same ladder. Completion additionally requires constrained routing,
provenance verification, recorded timing/resource reports, and explicit
disclosure of any uncovered timing paths.
