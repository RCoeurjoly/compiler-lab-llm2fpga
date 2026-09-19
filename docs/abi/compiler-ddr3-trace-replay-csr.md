# Temporary compiler-trace DDR3 replay diagnostic, ABI v1

This is **hand-written temporary diagnostic logic**, not compiler output and
not a production accelerator. It sends authenticated reference requests to the
production Wishbone ownership boundary and checks the responses from that
boundary. It neither authenticates files itself nor predicts DDR3 responses.
The host must verify the Task 1 receipt, binary digest, candidate, image,
prompt, token, and exact count before programming this device.

## Bus and window

The dedicated AXI-Lite slave uses byte addresses `0x900`–`0x97f`, a previously
unused sub-window in the pinned task6 BAR map. Existing loader registers are
unchanged. Integration must decode this window to this slave and leave all
other addresses routed to the existing task6 slave; do not connect two slave
responses together. This task defines the slave, not that top-level decoder.

The handshake follows
`/nix/store/p2fd086c91bii7c2r98kyc7lc5f6cmyp-task6_pcie_axil_rowstream_loader_ingress.v`:
AW and W are independently captured, a write executes once after both arrive,
and BVALID/BRESP remain stable until BREADY. RVALID/RDATA/RRESP remain stable
until RREADY. One transaction per direction is buffered. All clocks and
calibration/reset inputs are in the same clock domain; any CDC belongs outside
this slave. Ports use active-high synchronous `reset`, unlike task6's `rst_n`.

Only aligned 32-bit writes with `WSTRB=0xf` are supported. Malformed in-window
writes return SLVERR and latch protocol FAIL; writes outside the window return
SLVERR without changing diagnostic state. Unsupported/unaligned reads return
SLVERR and zero, without changing state. Successful transport returns OKAY;
hosts must separately check STATE/ERRORS for semantic command failures.

| Byte address | Access | Meaning |
|---|---|---|
| `0x900` | R | Diagnostic ID `0x52504c59` (RPLY) |
| `0x904` | R | ABI version `1` |
| `0x908` | W | COMMAND: exactly `1` START, `2` CLEAR, or `4` FINISH |
| `0x90c` | RW | Authenticated expected record count, unsigned 32-bit |
| `0x910` | W | Staged 32-bit Wishbone line address |
| `0x914`, `0x918`, `0x91c`, `0x920` | W | Staged expected response words 0–3 |
| `0x924` | W | PUSH: write exactly `1` after all five staging writes |
| `0x928` | R | STATE: `0` IDLE, `1` RUN, `2` PASS, `3` FAIL |
| `0x92c` | R | FLAGS bits: 0 calibration, 1 push-ready, 2 sealed, 3 starved |
| `0x930` | R | FIFO occupancy, 0–16 |
| `0x934` | R | Successfully pushed record count |
| `0x938` | R | Accepted Wishbone request count |
| `0x93c` | R | Terminated response count (ACK or ERR, counted once) |
| `0x940` | R | Compared ACK count (includes a mismatching ACK, excludes ERR) |
| `0x944` | R | First failure error bit |
| `0x948` | R | First failure zero-based record index; `0xffffffff` before failure |
| `0x94c` | R | First failure active line address |
| `0x950`, `0x954`, `0x958`, `0x95c` | R | First failure expected response words 0–3 |
| `0x960`, `0x964`, `0x968`, `0x96c` | R | First failure observed response words 0–3 |
| `0x970` | R | Staging-valid mask: bit 0 address, bits 1–4 data words 0–3 |

All other addresses, including reads of write-only registers, are reserved.
No byte-address-to-line-address translation is performed by the replay core.
The integration must ensure the 32-bit line address fits the actual controller
address width; do not silently truncate arbitrary host input.

## Record and lane order

Each Task 1 binary record is exactly 20 bytes: little-endian uint32 line address,
then 16 response bytes in Wishbone lane order. Write the address to `0x910`;
write the four little-endian uint32 response words to `0x914` through `0x920`
in order; then PUSH. Response byte 0 becomes `wb_rdata[7:0]`, byte 15 becomes
`wb_rdata[127:120]`. Example response bytes `00 11 22 33 ... ee ff` produce
words `33221100`, `77665544`, `bbaa9988`, `ffeeddcc`. PUSH snapshots all five
words and clears the staging-valid mask, so incomplete records cannot reuse
stale words from a previous PUSH. Each staging register may be rewritten before
PUSH; the latest fully written word wins.

## Producer sequence and backpressure

1. Read identity/version; CLEAR; configure the nonzero authenticated count
   (`13,116,912` for the accepted reference package). Configuration may only
   change while IDLE, before the first PUSH and before FINISH.
2. Wait for calibration and prefill up to 16 records, then START. Starting
   empty is allowed; FIFO starvation pauses without issuing traffic.
3. Stream the remaining records, retaining order and repeated addresses. A
   valid PUSH while full retains its AXI transaction and withholds BVALID until
   a slot becomes available. No entry is overwritten and no PUSH is counted
   twice under response backpressure. FIFO occupancy includes the active
   record until Wishbone accepts it. A full FIFO need not accept a simultaneous
   pop/push in the same cycle; the pending PUSH completes on the next cycle.
4. After the last PUSH has completed, issue FINISH exactly once to seal the
   stream. For traces fitting in the FIFO, FINISH may precede START. FINISH
   before the configured number of PUSHes latches terminal underflow. Ordinary
   empty FIFO periods before FINISH are **not** underflow.
5. Poll STATE. PASS requires FINISH plus exact equality of configured, pushed,
   accepted, responded, and checked counts and no active/pending transaction.
   Missing responses or missing FINISH never become PASS; enforce host-side
   timeouts. Before START, do not issue a seventeenth PUSH: it blocks the write
   channel, including a subsequent START. Poll space or START before refilling.

Wishbone uses `CYC/STB`, `WE=0`, `SEL=0xffff`; acceptance is `CYC && STB &&
!STALL`. Address and controls are held under stall. A synchronous FIFO read
loads one active register; only acceptance pops that FIFO entry. STB drops
after acceptance, CYC remains asserted until ACK/ERR, and no second request is
accepted until that response has been checked. Same-cycle acceptance/ACK is
supported. ERR takes precedence over ACK. Unsolicited responses when no
transaction is active, including late responses after FAIL, are ignored.

## Failure and reset semantics

Error bits, in priority order if simultaneous:

| Bit/value | Cause |
|---|---|
| 3 / `0x08` | `replay_reset` or CLEAR during RUN |
| 2 / `0x04` | Calibration lost during RUN |
| 7 / `0x80` | Malformed CSR command/record or count reconfiguration after lock |
| 4 / `0x10` | START outside IDLE, without calibration, or with zero count |
| 5 / `0x20` | FINISH with pushed count unequal to configured count |
| 6 / `0x40` | Extra PUSH, PUSH before count configuration, or PUSH after FINISH |
| 1 / `0x02` | Wishbone error response |
| 0 / `0x01` | Expected/observed 128-bit response mismatch |

FAIL, the first error bit, index, address, expected and actual data are captured
atomically and persist despite further commands, mismatching responses,
calibration changes, and `replay_reset`. Counters freeze at failure, including
bus events on the failure edge. The index is the number of ACKs compared before
the failure. For failure without an active record, address/expected are zero;
actual is the raw sampled bus data and is meaningful only for response failures.
PASS is retained absent further commands; an extra PUSH or illegal START can
still turn it into FAIL. Do not stream trailing records after a PASS snapshot.

`replay_reset` is a runtime abort, not a cold initialization signal: asserted
during RUN it produces persistent FAIL, never PASS. Calibration loss also
aborts even while waiting for input. Both suppress Wishbone traffic immediately.
CLEAR during RUN aborts to FAIL; a **second** CLEAR while FAIL is required to
discard the failure evidence and rearm. CLEAR outside RUN clears staging, FIFO,
counts, configuration, and failures to IDLE. It does not wait for external DDR
responses. Before CLEAR/restart after an abort, the integrator/host must drain
or reset the memory boundary so a late response cannot belong to a new run.

The separate cold `reset` clears all state to IDLE (arrays need not be cleared
because their occupancy/pointers are reset). It is intended for FPGA/system
initialization and is destructive to evidence, not a software replay abort.
Wire runtime replay resets to `replay_reset`, not to this cold-reset input.

## Verification scope

`nix develop .#default -c python3 -m unittest -v tests.test_compiler_ddr3_trace_replay`
tests the actual RTL and AXI-Lite interface, address/data mutations, and the
pinned production ownership mux. The latter is an explicit Nix-store input,
not a behavioral reimplementation. These unit/transport checks are not evidence
of FPGA resource/timing closure, PCIe electrical behavior, calibration on a
board, or Micron-model/hardware replay completion.
