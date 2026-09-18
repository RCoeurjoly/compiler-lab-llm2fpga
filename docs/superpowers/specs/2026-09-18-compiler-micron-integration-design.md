# Compiler TinyStories-1M with physical-interface DDR3 simulation

## Approved objective and ordering

Validate the existing compiler-generated TinyStories-1M implementation through
the pinned UberDDR3 controller and PHY and a Micron DDR3 memory model before
another synthesis/routing attempt. Then validate the approved request-bank
consolidation against the same harness. Board first-token inference remains
the destination; neither simulation nor successful loading completes the goal.

This simulation gate precedes implementation of
`2026-09-18-compiler-ddr3-bank-consolidation-design.md`. The old abstract-memory
first-token test remains a fast regression, not evidence of DDR3 PHY coverage.

## Frozen integration boundary

Retain the payload-reset compiler candidate and authenticated image identified
by `artifacts/diagnostics/2026-09-18-owner-mux-simulation/result.json`.
Instantiate the existing command adapter, backend, 240-port arbiter and owner
mux. Replace only the testbench's abstract memory with the pinned `ddr3_top`,
controller, PHY and Micron memory model connected at DDR pins.

Host transactions initially enter the owner mux at Wishbone. This does not
cover PCIe TLP ingress, PCIe reset/clock crossings or the complete board shell.
Keep these omissions explicit in every result. Do not change the production
PCIe or DDR3 implementation to make the testbench pass. Behavioral vendor I/O
models and ideal clocks are test infrastructure, not accelerator deliverables.

Use the board parameters, not standalone-testbench defaults:

- Controller/DDR periods: 12,000/3,000 ps; two byte lanes, x16 data.
- Row/column/bank address widths: 15/10/3; 25-bit burst Wishbone addresses,
  128-bit Wishbone data, 16 byte enables, one rank.
- `SDRAM_CAPACITY=4`, `SPEED_BIN=1`, `ODELAY_SUPPORTED=0`, `DLL_OFF=0`.
- `TRCD=13750`, `TRP=13750`, `TRAS=35000` ps.
- `BIST_MODE=2`, `BIST_TEST_DATAMASK=0`, `ECC_ENABLE=0`, `SECOND_WISHBONE=0`.
- `MICRON_SIM=0`: production startup waits and full BIST address range.

The pinned controller's `MICRON_SIM=1` reduces `wb_addr_bits_sim` to eight,
shortens two startup waits by 500 and accelerates UART behavior. It is NOT
solely a startup-delay switch and is not acceptable for this gate. Do not force
calibration completion, alter BIST counters or reduce the memory geometry.

The bundled `den8192Mb`/x16 parameters have 16 row bits, unlike the board.
Use authentic Micron 4096-Mbit/x16 parameters with 15 row bits. A local source
is available at
`/home/roland/Vivado/2025.2.1/data/ip/xilinx/ddr3_v1_4/data/dlib/ultrascale/ddr3_sdram/tb/ddr3_model/4096Mb_ddr3_parameters.vh`.
Its SHA-256 is `6414a811a8feed2acd874ad68bd2e02b935b2f81fdc9a294d2f8d511e9d65941`.
The initially identified `rsb/non_default_iprepos/micron_ddr3_v2_0` copy is
incompatible: it initializes three ZQ timing variables that the pinned model
continuously drives. The selected copy leaves those declarations uninitialized,
matching the model; neither vendor source is patched.
Check compatibility with the pinned model during elaboration. Record both
sources and hashes; do not silently substitute the installed model or copy
vendor files into the repository without redistribution review. The existing
8192-Mbit parameter filename is not evidence of board compatibility.

## Test sequence and observations

1. Elaborate the memory model with explicit density, width and speed macros;
   assert row/column/bank/data geometry and strict timing checks at runtime.
2. Run production-duration reset, initialization, calibration and full BIST.
   Record phase transitions and errors without overriding DUT state. Measure
   simulator throughput in a bounded run before budgeting a full test.
3. Write all 4,136,720 authenticated image bytes through the real controller,
   then read every byte back. No hierarchical preload or `$readmemh` into the
   Micron memory. A host-side input-file buffer is allowed.
4. Supply prompt tokens `[7454,2402,257,640]` to the real command adapter and
   start the unchanged compiler accelerator. Require first token 11.
5. Record accepted requests, responses, addresses, data, errors, outstanding
   balance, phase/cycle counts and output handshake. Check stable requests
   under backpressure and drain all transactions. Classify diagnostics by
   controller, PHY/model, adapter and accelerator boundary.
6. Repeat after compiler-owned bank consolidation; compare architectural
   results and per-consumer transaction semantics, allowing latency changes.

Model timing violations, unknown returned data, lost responses, unmatched
completions or incorrect readback fail the applicable gate. A calibrated-only
run is not load acceptance; a load-only run is not inference acceptance.
Negative controls must demonstrate that corruption and timeout are rejected.

## Practical execution and completion

Use Nix-provided tools and Python, bounded commands, and test-specific scratch
directories. Explicitly set the Micron model's backing-file directory rather
than allowing shared `/tmp` filenames. Check disk headroom before full BIST:
the model's file-backed storage can touch the complete configured address space.
Do not waive BIST or preload memory to hide a runtime problem. Report measured
costs and reassess the simulator if the full gate is impractical.

Do not launch synthesis/P&R until the functional simulation gates pass. Then
require completed routing, fixed-clock reports, provenance and board first-token
evidence. Preserve loader-only and compiler baselines. Keep known nextpnr
cell-timing coverage limitations explicit; simulated protocol timing does not
prove placed/routed electrical timing or full autoregressive inference.
