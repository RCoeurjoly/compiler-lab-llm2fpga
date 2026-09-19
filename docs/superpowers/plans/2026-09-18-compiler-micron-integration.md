# Compiler TinyStories-1M Fast DDR3 Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the current compiler-generated TinyStories-1M first token on
YPCB through PCIe and production UberDDR3, using a streamed exact-trace
hardware checkpoint before the full accelerator and before bank consolidation.

**Architecture:** Transaction-level simulation authenticates the full model
load, token `11`, and ordered request/response trace. A host utility converts
that trace into fixed-width replay records and streams them over PCIe to a
small diagnostic FIFO; the replay core issues the same ordered DDR3 reads and
compares every response. Only a passing loader and trace bitstream permits a
full accelerator build; the approved 197-bank consolidation comes last.

**Tech Stack:** Nix Python, pytest/unittest, Verilator, SystemVerilog, Yosys,
nextpnr-xilinx/openXC7, the pinned PCIe/UberDDR3 source closure, and YPCB
hardware through the established deferred-authorization protocol.

**Spec:**
`docs/superpowers/specs/2026-09-18-compiler-micron-integration-design.md`

## Global Constraints

- Preserve the authenticated 4,136,720-byte image with SHA-256
  `e44d9bac0ddcf267cb2b41eb6f0aee623bacfb28809d9dffb7edc0319c43e593`,
  prompt `[7454,2402,257,640]`, expected token `11`, and compiler arithmetic.
- Never reuse kev-gpt accelerator RTL. It is not an implementation input.
- Preserve PCIe, two DDR3 byte lanes, 333/83.33 MHz DDR/controller clocks,
  production `BIST_MODE=2`, board clocks, XDC, and timing constraints.
- Transaction simulation starts at Wishbone and does not validate PCIe or
  physical DDR3; every receipt must say so.
- The trace replayer is temporary diagnostic RTL, not compiler output or a
  production datapath substitute.
- Stream the exact authenticated trace; do not replace it with arbitrary
  synthetic pressure or a shorter prefix for acceptance.
- Stop at the first failing gate and retain first-mismatch evidence before any
  implementation change.
- Preserve loader-only and passing compiler baselines. Do not overwrite their
  receipts or accepted bitstreams.
- Use Nix-provided Python and tools. Give every long command an explicit wall
  bound and record terminal status; never silently extend it.
- Micron-model simulation is optional diagnostic evidence, not an acceptance
  gate. First-token success is not full autoregressive inference.

## Review Focus

- A truncated, reordered, duplicated, or trailing trace record must be rejected
  before hardware transfer; Task 1 tests each case.
- FIFO backpressure or PCIe pauses must not reorder, duplicate, or drop replay
  records; Task 2 drives adversarial stalls and proves exact counts.
- A DDR response with the correct address but wrong data must latch the first
  mismatch once and preserve it until explicit clear; Task 2 tests this.
- Reset, calibration loss, or PCIe lifecycle interruption during replay must
  produce a terminal non-pass receipt and never a partial success; Tasks 2 and
  4 test these cases.
- Passing synthesis/routing with uncovered paths must not be promoted as a
  qualified bitstream; Tasks 3–6 require timing-coverage disclosure.

---

### Task 1: Authenticate a streamable exact first-token replay package

**Files:**
- Create: `scripts/analysis/build_compiler_trace_replay.py`
- Create: `tests/test_compiler_trace_replay.py`
- Create: `artifacts/reference/tinystories-1m-compiler-ddr3-trace-replay.json`
- Modify: `artifacts/diagnostics/2026-09-18-owner-mux-simulation/README.md`

**Interfaces:**
- Consumes: alternating ASCII request records carrying sequence/address and
  response records carrying sequence/address/data from
  `reference_memory_trace.sv`, plus the
  authenticated model/candidate receipts.
- Produces: `build_replay(trace: Path, output: Path, bindings: dict) -> dict`.
  The binary format is 20 bytes per request: little-endian `uint32 address`
  followed by the exact 16 response bytes in Wishbone lane order. The manifest
  records schema `tinystories-1m-compiler-trace-replay-v1`, record count,
  binary SHA-256, source trace SHA-256, candidate SHA-256, image SHA-256,
  prompt, token, and byte order.

- [ ] **Step 1: Write failing parser/authentication tests**

  Add fixtures with two valid pairs and mutations for a missing response,
  response-address mismatch, duplicate sequence, reordered pair, trailing
  garbage, changed response data, and wrong binding hash. Assert the valid
  output equals:

  ```python
  struct.pack("<I", 0x87F0) + bytes.fromhex("1e1d6209010180020000000000000000")
  ```

  followed by the second record. Assert every mutation raises
  `TraceReplayError` before replacing the output path.

- [ ] **Step 2: Run the focused tests and observe RED**

  Run:

  ```sh
  nix develop .#default -c python3 -m unittest -v tests.test_compiler_trace_replay
  ```

  Expected: failure because `build_compiler_trace_replay.py` does not exist.

- [ ] **Step 3: Implement the bounded-memory converter**

  Parse one Q/R pair at a time, hash the original bytes while reading, write to
  a sibling temporary file, `fsync`, and rename only after validating EOF and
  all supplied bindings. Do not load the 892-MiB trace into memory. Expose:

  ```python
  class TraceReplayError(ValueError): ...
  def build_replay(trace: Path, output: Path, bindings: dict[str, object]) -> dict[str, object]: ...
  ```

  The CLI requires `--trace`, `--output`, `--candidate-sha256`,
  `--image-sha256`, `--prompt 7454,2402,257,640`, `--token 11`, and
  `--manifest-output`.

- [ ] **Step 4: Run positive and negative tests**

  Run the focused test above and:

  ```sh
  nix develop .#default -c python3 -m unittest -v tests.test_compare_memory_traces
  ```

  Expected: all pass.

- [ ] **Step 5: Materialize and independently verify the authenticated package**

  Regenerate the raw trace if its recorded scratch path is unavailable. Build
  the binary from `/tmp/compiler-reference-trace.41e2QX/reference.trace`, then
  independently stream-check all 13,116,912 records against the binary and the
  authenticated image. Store the compact JSON manifest in Git; keep the
  approximately 262-MiB binary in a hashed Nix/scratch artifact, not Git.

- [ ] **Step 6: Commit the trace package tooling and receipt**

  ```sh
  git add scripts/analysis/build_compiler_trace_replay.py \
    tests/test_compiler_trace_replay.py \
    artifacts/reference/tinystories-1m-compiler-ddr3-trace-replay.json \
    artifacts/diagnostics/2026-09-18-owner-mux-simulation/README.md
  git commit -m "test: authenticate compiler DDR3 replay stream"
  ```

### Task 2: Build the bounded streamed trace-replay core and CSR contract

**Files:**
- Create: `rtl/diagnostics/compiler_ddr3_trace_replay.sv`
- Create: `rtl/diagnostics/compiler_ddr3_trace_replay_csr.sv`
- Create: `tests/rtl/compiler_ddr3_trace_replay_tb.sv`
- Create: `tests/test_compiler_ddr3_trace_replay.py`
- Create: `docs/abi/compiler-ddr3-trace-replay-csr.md`

**Interfaces:**
- Consumes: a 32-bit CSR write stream containing five words per replay record
  (`address`, then expected response words 0–3), followed by `PUSH`; calibration
  state and a single-outstanding 128-bit Wishbone read port.
- Produces: a depth-16 record FIFO; `wb_cyc/stb/we/address/sel`; persistent
  `state`, accepted/response/checked counters, FIFO level, first mismatch index,
  address, expected data, actual data, and error bits. `START` is legal only
  after calibration and an authenticated expected-record count is configured.

- [ ] **Step 1: Write the failing RTL contract test**

  Exercise five records with stalls before acceptance and responses, including
  repeated addresses. Require `wb_we=0`, `wb_sel=16'hffff`, stable requests
  while stalled, exact request order, and exact terminal count. Add separate
  cases for FIFO-full backpressure, response error, wrong data, reset during
  replay, calibration loss, early START, underflow, extra record, and clear.
  The wrong-data case must prove the first mismatch remains unchanged after a
  second mismatch.

- [ ] **Step 2: Run the RTL test and observe RED**

  ```sh
  nix develop .#default -c python3 -m unittest -v tests.test_compiler_ddr3_trace_replay
  ```

  Expected: failure because the replay modules do not exist.

- [ ] **Step 3: Implement the minimal replay engine**

  Use one active record and a 16-entry synchronous FIFO. Pop only when the
  Wishbone request is accepted; compare the corresponding ACK data before
  accepting another request. Define terminal states `IDLE`, `RUN`, `PASS`, and
  `FAIL`; make `PASS` require configured count equals pushed, accepted,
  responded, and checked counts. Latch the first failure atomically.

- [ ] **Step 4: Implement and document the CSR adapter**

  Use the existing task6 CSR handshake style. Allocate a versioned diagnostic
  sub-window without changing existing loader registers. Specify offsets,
  access widths, reset behavior, producer backpressure, START/CLEAR semantics,
  and the exact word/lane order in
  `docs/abi/compiler-ddr3-trace-replay-csr.md`.

- [ ] **Step 5: Run mutation and regression tests**

  Run the focused test, command-adapter tests, owner-mux checks, and mutate the
  request-address register and first-mismatch latch independently. Expected:
  baseline passes and both mutations fail their owning assertions.

- [ ] **Step 6: Commit the replay core**

  ```sh
  git add rtl/diagnostics tests/rtl/compiler_ddr3_trace_replay_tb.sv \
    tests/test_compiler_ddr3_trace_replay.py \
    docs/abi/compiler-ddr3-trace-replay-csr.md
  git commit -m "feat: add streamed compiler DDR3 trace replay"
  ```

### Task 3: Pin and integrate the replay core into the proven board shell

**Files:**
- Create: `scripts/pipeline/materialize_task6_board_shell.py`
- Create: `tests/test_task6_board_shell_closure.py`
- Create: `rtl/diagnostics/compiler_ddr3_trace_replay_top.sv`
- Create: `tests/test_compiler_ddr3_trace_replay_top.py`
- Modify: `flake.nix`
- Modify: `scripts/analysis/check_compiler_shell_status.py`

**Interfaces:**
- Consumes: the exact loader shell repaired at LLM2FPGA commit `e368449`, its
  PCIe/UberDDR3 dependencies, the replay core, and the production XDC/tool pins.
- Produces: a content-hashed source-closure derivation and a replay-top netlist
  where the existing loader owns DDR3 until START, then the replay core owns it
  until PASS/FAIL. Existing loader register behavior remains byte-for-byte
  compatible.

- [ ] **Step 1: Write failing source-closure tests**

  Require an explicit repository commit and per-file hashes; reject a dirty
  ambient checkout, missing source, changed loader CSR offset, one-lane DDR3,
  non-production BIST, or a source named like the expected file with a wrong
  hash. The materializer must never read `/tmp` as a long-term source.

- [ ] **Step 2: Materialize the pinned board-shell closure**

  Implement a Nix-facing manifest generator patterned after
  `materialize_ddr3_source_closure.py`. Pin the exact PCIe endpoint, loader,
  owner mux, UberDDR3, clock wrapper, XDC, and tool arguments used by the
  proven loader receipt. Record AGPL/source provenance separately from the
  compiler-generated accelerator provenance.

- [ ] **Step 3: Write the failing integrated-top tests**

  Simulate host load transactions, full readback on a small fixture, owner
  handoff, replay stalls, PASS, mismatch, and clear/rearm. Assert that host and
  replay ACKs are never delivered simultaneously and that ownership cannot
  change with an outstanding request.

- [ ] **Step 4: Integrate without modifying PCIe or UberDDR3 internals**

  Add the CSR sub-window and replay ownership as new wrapper logic. Preserve
  the fixed two-lane 333/83.33 MHz profile and all existing constraints. Expose
  calibration/BIST state and replay diagnostics through BAR0.

- [ ] **Step 5: Run integration, synthesis, and timing-screen tests**

  Run the focused simulations, `yosys check`, resource accounting, and bounded
  placement-only diagnostics. Require a completed result and reject undriven
  watched nets. Placement is screening evidence only; do not promote a
  bitstream yet.

- [ ] **Step 6: Commit the pinned replay integration**

  ```sh
  git add scripts/pipeline/materialize_task6_board_shell.py \
    tests/test_task6_board_shell_closure.py \
    rtl/diagnostics/compiler_ddr3_trace_replay_top.sv \
    tests/test_compiler_ddr3_trace_replay_top.py \
    scripts/analysis/check_compiler_shell_status.py flake.nix
  git commit -m "feat: integrate exact trace replay with YPCB loader"
  ```

### Task 4: Automate and pass loader plus exact-trace YPCB gates

**Files:**
- Create: `scripts/pipeline/run_compiler_ddr3_trace_replay.py`
- Create: `tests/test_run_compiler_ddr3_trace_replay.py`
- Create: `artifacts/reference/compiler-ddr3-trace-replay-bitstream.json`
- Create: `docs/results/2026-09-19-compiler-ddr3-trace-replay-hardware.md`

**Interfaces:**
- Consumes: PCI BDF selected by the established lifecycle protocol, exact
  bitstream/source receipt, authenticated model image, and Task 1 replay
  package.
- Produces: one JSON receipt containing lifecycle evidence, calibration/BIST,
  complete load/readback hash, replay package identity, exact counters,
  terminal state, first mismatch diagnostics, elapsed time, and all relevant
  artifact hashes.

- [ ] **Step 1: Write controlled-device tests for the host runner**

  Model BAR0 and lifecycle commands. Cover success, wrong endpoint identity,
  missing BAR, calibration failure, image hash mismatch, readback mismatch,
  FIFO backpressure, early PASS, replay FAIL, timeout, endpoint disappearance,
  and stale status from a prior run. Require nonzero exit and an atomic failed
  receipt for every negative case.

- [ ] **Step 2: Implement the streaming host runner**

  Use only Nix Python. Verify bitstream/source/image/replay hashes before MMIO.
  Use the established deferred-authorization protocol; do not perform unsafe
  bridge removal/rescan or require host reboot. Load and verify every model
  line before CLEAR/START. Stream records only when FIFO space is reported and
  require exact terminal counters before accepting PASS.

- [ ] **Step 3: Build and qualify the replay bitstream**

  Run Yosys and constrained nextpnr-xilinx with the pinned seed/tool/XDC.
  Require FASM/bitstream conversion, completed fixed-clock reports, no weakened
  constraints, and an explicit list of uncovered cell timings. Record hashes
  before programming.

- [ ] **Step 4: Program and run the YPCB gates**

  Program SRAM/BPI through the existing sudoless workflow, use the automated
  chassis/lifecycle recovery when necessary, then require production BIST,
  complete PCIe image readback, and all 13,116,912 exact replay comparisons.
  Repeat a failed chunk only for localization; do not shorten acceptance.

- [ ] **Step 5: Preserve hardware evidence and commit**

  Record the exact first mismatch on failure. On success, preserve the
  bitstream receipt and hardware report; do not call this inference.

  ```sh
  git add scripts/pipeline/run_compiler_ddr3_trace_replay.py \
    tests/test_run_compiler_ddr3_trace_replay.py \
    artifacts/reference/compiler-ddr3-trace-replay-bitstream.json \
    docs/results/2026-09-19-compiler-ddr3-trace-replay-hardware.md
  git commit -m "test: qualify compiler DDR3 trace replay on YPCB"
  ```

### Task 5: Prove the unchanged compiler accelerator on YPCB

**Files:**
- Modify: the pinned compiler board-top generation/integration target in
  `flake.nix`
- Modify: `scripts/pipeline/run_compiler_ddr3_trace_replay.py` only to share
  lifecycle/load/readback helpers; do not put inference semantics in it
- Create: `scripts/pipeline/run_compiler_ddr3_first_token.py`
- Create: `tests/test_run_compiler_ddr3_first_token.py`
- Create: `artifacts/reference/compiler-ddr3-first-token-bitstream.json`
- Create: `docs/results/2026-09-19-compiler-ddr3-first-token-hardware.md`

**Interfaces:**
- Consumes: the same pinned shell and model image that passed Task 4, unchanged
  compiler-generated accelerator/adapter/backend sources, prompt
  `[7454,2402,257,640]`, and expected token `11`.
- Produces: a timing/provenance receipt and a hardware inference receipt with
  load/readback, prompt, token, request/response counters, error status, and
  elapsed time.

- [ ] **Step 1: Write controlled-device first-token tests**

  Cover exact success, wrong prompt echo, premature ready, token mismatch,
  request/response imbalance, accelerator error, output timeout, stale token,
  and token backpressure/retirement. Require first-mismatch diagnostics in
  every failed receipt.

- [ ] **Step 2: Re-run the fast semantic gate from clean inputs**

  Regenerate the candidate and image through the compiler pipeline, verify all
  Task 1 hashes, run complete transaction-level load/readback and inference,
  and require token `11` with 13,116,912 balanced transactions. Explicitly
  record that PCIe and physical DDR3 remain outside this simulation.

- [ ] **Step 3: Integrate the unchanged compiler accelerator**

  Replace only the temporary replay owner with the authenticated compiler
  command adapter/backend/arbiter. Keep the loader, PCIe, UberDDR3, clocks,
  constraints, source closure, and diagnostics unchanged. Do not apply the
  197-bank consolidation yet.

- [ ] **Step 4: Build, route, and qualify the full bitstream**

  Run synthesis and constrained routing once the semantic receipt is green.
  If timing fails, preserve the exact critical path and stop; do not weaken the
  333/83.33 MHz DDR profile or constraints. If routing passes, verify source,
  netlist, FASM, bitstream, tool, timing, and image hashes.

- [ ] **Step 5: Run first-token hardware inference**

  Require production BIST, complete PCIe load/readback, exact prompt, token
  `11`, balanced counters, no error, and completion within the declared
  300-second inference bound. A mismatch must be classified using the already
  passing trace-replay boundary before any RTL fix.

- [ ] **Step 6: Commit the unchanged-accelerator acceptance evidence**

  ```sh
  git add flake.nix scripts/pipeline/run_compiler_ddr3_first_token.py \
    tests/test_run_compiler_ddr3_first_token.py \
    artifacts/reference/compiler-ddr3-first-token-bitstream.json \
    docs/results/2026-09-19-compiler-ddr3-first-token-hardware.md
  git commit -m "test: prove compiler DDR3 first token on YPCB"
  ```

### Task 6: Apply and requalify the 197-bank compiler consolidation

**Files:**
- Modify: compiler externalization/pass files named by
  `docs/superpowers/specs/2026-09-18-compiler-ddr3-bank-consolidation-design.md`
- Modify: their focused tests
- Create: `artifacts/reference/compiler-ddr3-consolidated-first-token-bitstream.json`
- Create: `docs/results/2026-09-19-compiler-ddr3-consolidation-hardware.md`

**Interfaces:**
- Consumes: the passing Task 5 compiler source, image, ABI, trace package,
  board shell, and acceptance commands.
- Produces: compiler-generated consolidated RTL with the same observable
  semantics and the complete repeated acceptance ladder.

- [ ] **Step 1: Re-read the consolidation spec and write failing compiler tests**

  Require exactly 197 immutable learned-weight banks to share the approved
  request-controller structure while preserving the 240-slot ABI, selected
  response ownership, byte extraction, reset/rearm, and external memory map.
  Mutate bank selection and response ownership separately and require failure.

- [ ] **Step 2: Implement the minimum compiler-owned consolidation**

  Change the lowering/externalization pass, not generated output with `sed` and
  not handwritten accelerator RTL. Regenerate all affected RTL and provenance.

- [ ] **Step 3: Repeat semantic and exact-trace gates**

  Require full image load/readback, token `11`, balanced transactions, and an
  authenticated consolidated trace. Compare the trace to the approved semantic
  allowances; do not assume byte identity if arbitration latency changes.

- [ ] **Step 4: Repeat synthesis, routing, loader, and trace replay**

  Use unchanged PCIe/UberDDR3 sources, profile, clocks, constraints, and host
  runners. Record resource/timing deltas against Task 5 and require the complete
  hardware image readback and exact consolidated trace.

- [ ] **Step 5: Repeat full first-token hardware inference**

  Require token `11`, balanced diagnostics, no errors, and the 300-second
  bound. Preserve timing coverage limitations and do not claim multi-token
  inference.

- [ ] **Step 6: Run the completion audit and commit**

  Verify every spec requirement against source, simulation, route, bitstream,
  and hardware receipts. Commit only if the entire repeated ladder passes:

  ```sh
  git add scripts/analysis/externalize_compiler_memory.py \
    tests/test_externalize_compiler_memory.py \
    tests/test_compiler_external_memory_contract.py \
    tests/test_select_external_memory_bank.py \
    artifacts/reference/compiler-ddr3-consolidated-first-token-bitstream.json \
    docs/results/2026-09-19-compiler-ddr3-consolidation-hardware.md
  git commit -m "feat: qualify consolidated compiler DDR3 inference"
  ```
