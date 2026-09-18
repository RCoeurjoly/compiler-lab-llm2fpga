# Physical DDR3 simulation gate

The initial `profile` phase elaborates the actual pinned Micron model with a
4-Gbit x16 parameter file and verifies geometry and strict-check settings.
It does **not** exercise initialization, calibration, loading or inference.
The `startup` phase instantiates the pinned controller and PHY, uses production
waits and full BIST geometry, and requires natural calibration/BIST completion.
The `load` and `infer` phases connect the authenticated compiler and production
ownership mux to the physical memory harness; their full-runtime acceptance
has **not** passed.

Run from the repository root:

```sh
nix develop .#default -c env \
  UBERDDR3_SOURCE=/nix/store/i51l5i03r7vw52aajgh0nxqj0w94v8cj-task6-ypcb-uberddr3-source \
  MICRON_PARAMETERS=/home/roland/Vivado/2025.2.1/data/ip/xilinx/ddr3_v1_4/data/dlib/ultrascale/ddr3_sdram/tb/ddr3_model/4096Mb_ddr3_parameters.vh \
  python3 -m unittest discover -s tests -p test_compiler_micron_profile.py
```

Without explicit external inputs these tests skip; a skip is not acceptance.
The parameter file remains outside the repository. Its SHA-256 is
`6414a811a8feed2acd874ad68bd2e02b935b2f81fdc9a294d2f8d511e9d65941`.
The pinned `testbench/ddr3.sv` SHA-256 is
`1a061f47ec3178c60a05e79be283ccf6dab5f4ccba64a2707eb2fc68f26d1c67`.

On 2026-09-18, all three tests passed with Nix Icarus 12.0: correct geometry,
deliberately wrong row width rejected by `$fatal`, and missing vendor input
rejected. The earlier `rsb/non_default_iprepos` parameter file failed elaboration
because its ZQ variable initializers conflict with the pinned model's continuous
assignments. The compatible vendor file requires no patch.

For retained logs, invoke `bash scripts/analysis/run_compiler_micron_sim.sh`
with `--phase profile --work-dir PATH --uberddr3-source PATH
--vendor-parameters PATH`. The runner records source hashes, compile/run logs,
and a unique memory backing directory. `--negative-control wrong-geometry`
must fail. These are testbench sources only; no accelerator or transport RTL
has been changed. PCIe ingress is not simulated here.

## Startup harness and limitations

Use the same runner with `--phase startup`. A 1,800-second simulator wall bound
is the default; `--max-cycles N` additionally bounds controller cycles. Neither a
timeout nor calibration-in-progress is a pass. The startup harness observes
state transitions, BIST counters and errors. It does not inject host requests.

Six regression tests pass, including an uncalibrated watchdog, rejection of
`MICRON_SIM=1`, and a real pin-level Micron initialization timing violation.
The last test demonstrates that vendor `$display` errors must override a zero
simulator exit and any earlier profile success message. Missing terminal
acceptance markers also fail.

The first exploratory run exposed a testbench clock-phase mistake: starting
all clocks low puts controller rising edges halfway between DDR rising edges.
The board PLL has zero-phase controller/DDR outputs. The harness now matches
that alignment (as does the upstream bench), with a regression assertion that
was observed failing before the correction. This is a stimulus correction,
not a controller/accelerator RTL change or evidence that board calibration is
fixed. The exploratory run was stopped and is not an acceptance result.

`--wall-seconds N` permits an explicit longer budget only for the combined
`load` or `infer` phases (maximum 259,200 seconds / 72 hours). Profile and
standalone-startup development runs remain capped at 1,800 seconds. The runner
records its selected limits, start/finish times and exit status in the work
directory. Missing terminal markers and model errors still reject the result.

Simulation differences remain explicit:

- Ideal clocks; no physical jitter, skew, routing delay or signal-integrity model.
- `SIM_MODEL` selects upstream behavioral FPGA I/O primitives. `NO_TEST_MODEL`
  disables their parallel comparisons against proprietary primitive models.
- The behavioral IDELAYCTRL asserts readiness 10 ns after reset release;
  IDELAYE2 models a 600-ps base delay plus 78 ps per tap. This does not establish
  real PHY electrical qualification.
- Micron `DEBUG=0` suppresses per-beat information, not strict timing/mode errors;
  the real-error regression passes with this setting. No memory preload,
  calibration forcing or `MICRON_SIM` acceleration is enabled.
- Icarus reports existing upstream width-pruning warnings and two constant-only
  `always @*` blocks with empty sensitivity lists (disabled ECC muxes and unused
  second Wishbone outputs). Logs retain them; no vendor RTL has been patched.

Passing these harness tests is **not** passing full startup, loading or inference.

## Compiled-simulator cross-check

The runner also accepts `--simulator xsim --xsim-bin PATH`. The installed path
used here is `/home/roland/Vivado/2025.2.1/Vivado/bin`. This selects **simulation
only**: it does not replace the production synthesis or routing flow. Execute
outside the restricted process sandbox if XSim's local IPC fails to initialize.
All simulator scratch files are created in the selected work directory.

To repeat the six tests under XSim, add these variables to the `env` command
above:

```sh
MICRON_SIMULATOR=xsim XSIM_BIN=/home/roland/Vivado/2025.2.1/Vivado/bin
```

All six tests passed under XSim 2025.2.1 in 32.786 seconds on 2026-09-18. XSim
returns zero even for the deliberate `$fatal` watchdog in this setup; the
runner's diagnostic/terminal-marker checks are therefore mandatory.

A separate 100,000-cycle benchmark completed in 23.38 wall seconds. Icarus
reached the same observation after roughly four minutes and was subsequently
stopped to use the faster simulator; neither run passed full BIST. At that
observation, both had state 17 (burst write), instruction 22, write counter
38,644, read counter zero and zero recorded BIST read errors. Zero read errors
here is **not readback evidence**: the burst-read phase had not started.

The first two reset observations differ (initial instruction X versus zero,
and reset-state entry at cycle 1 versus 2). The remaining 87 recorded
observations match exactly, from read-training entry at cycle 58,524 through
the 100,000-cycle observation. Full bus-trace equivalence is not claimed.

Preserved benchmark logs are in
`artifacts/diagnostics/2026-09-18-micron-startup-benchmark/` together with the
source hashes. Original scratch locations:

- Icarus: `/tmp/compiler-micron-aligned.Rgr682/run.log`, SHA-256
  `9ffc9168151e4a8a36d1640563c6e5816c1274003414ed90cfb892a2963beb2d`.
- XSim: `/tmp/compiler-micron-xsim.9jDRs4/benchmark-unsandboxed.log`, SHA-256
  `5e752100a43d7715482eb5c088f05c9e90ceac704ce1d38cef45b69b032984e8`.

These short benchmarks measure execution cost and agreement during startup;
they do not authorize reducing memory geometry or bypassing full BIST.

The sustained million-cycle benchmark ended at its deliberate watchdog with
888,979 BIST writes and no reads, using 350.460 seconds of XSim CPU time. Its
terminal status is a rejected, incomplete startup run, not a BIST pass. At this
measured rate a single 33,554,432-address write sweep is roughly four hours;
other BIST patterns and inference add substantial time. No long qualification
run has yet been accepted or silently extended.

## Compiler integration harness

For `--phase load|infer`, also supply `--model PATH --image PATH`. The runner
checks both inputs against the frozen pre-consolidation owner-mux receipt and
image manifest before compilation. It uses the same pinned adapter, backend,
240-port arbiter and owner mux as the passing abstract-memory simulation.

The bench holds the accelerator and owner mux in reset until natural DDR
calibration/full BIST completion. It then sends every image byte through host
Wishbone writes and compares every readback line before supplying the frozen
prompt. A host-side `$fread` buffer is stimulus, not a DDR memory preload.
`infer` additionally requires token 11, balanced accelerator transactions and
five cycles of output backpressure. An ordered request/response trace goes to
`accelerator-memory.trace`; hash that completed file for a result receipt.
`--negative-control corrupt-write` intentionally corrupts line 17 and must fail
readback before inference. This physical readback negative control is still
pending full-runtime execution.

Two fast integration tests check that the real combined hierarchy elaborates
and rejects an uncalibrated watchdog with zero host requests, and that a wrong
image fails authentication before elaboration. They do not test the post-BIST
load/inference path. Enable them with `MICRON_MODEL` and `MICRON_IMAGE` in
addition to the other external-input variables, and run
`python3 -m unittest discover -s tests -p test_compiler_micron_integration.py`
inside the Nix shell.

XSim uses `xvlog --relax` for pinned `input logic` declarations under
`default_nettype none`, and `xelab --timescale 1ps/1ps` for compiler primitives
without an explicit timescale. These options do not modify the input files or
override explicitly declared PHY/model time units. Runtime Micron timing and
mode-register checks remain enabled and covered by negative tests. PCIe ingress,
the board reset shell and asynchronous clock crossings remain outside this
Wishbone-injected simulation.

The integrated 100,000-cycle startup probe also reached BIST state 17 with
write counter 38,644, exactly matching the standalone observation. Host and
accelerator request counts remained zero. It stopped at the deliberate
watchdog with runner exit 1; XSim reported 43.760 CPU seconds. The saved
`compiler-integrated.log` and `compiler-integrated-sources.sha256` are in the
benchmark artifact directory above. This proves neither full BIST nor model
readback. The real memory model also warns that automatic self-refresh is not
modeled; that coverage limitation remains, rather than being suppressed.

### First full combined run budget

Use a 72-hour wall cap and 1,000,000,000-controller-cycle watchdog for the
first combined run. This is an upper limit, not a predicted completion time
or permission to extend a timed-out job. Full BIST-2 involves roughly six
33,554,432-address sweeps, with additional stalls for random-row accesses.
The measured million-cycle standalone run and integrated 100,000-cycle probe
put this in the tens-of-hours range, before inference. The combined bench
avoids repeating startup between BIST, load/readback and token generation.

Monitor the first evidenced error and disk headroom while it runs. Do not
modify the runner or testbench in place during execution, restart a live
process, or interpret partial BIST progress as acceptance. After a terminal
result, retain logs/trace hashes and classify the earliest failed gate before
any implementation changes. Source changes and qualification runs remain
separate: no bank consolidation, synthesis or routing before the required
functional gates pass.
# Ordered abstract-memory reference trace

`reference_memory_trace.sv` is a test-only single-outstanding observer.
Add it and `reference_memory_trace_bind.sv` to the Verilator build documented
in `artifacts/diagnostics/2026-09-18-owner-mux-simulation/README.md`, using a
fresh build directory, and run with `+TRACE_FILE=/path/to/reference.trace`.
The binding observes the accelerator side of the production ownership mux;
host model-loading traffic is deliberately excluded. Neither the compiler
RTL nor the baseline wrapper/driver is modified.

Each accepted request emits `Q <sequence> <32-bit line address>`; its response
emits `R <sequence> <retained address> <128-bit data>`, matching the physical
DDR testbench format. Stalled attempts do not create entries. Overlapping
requests and responses without outstanding requests fail the simulation.
This observer expects one initial reset and delayed responses, as used by
these harnesses; it is not a general pipelined Wishbone monitor.

The observer regression runs with
`python3 -m unittest discover -s tests -p test_reference_memory_trace.py`
inside the Nix development environment. A trace is a reference only after
the associated full-image readback and authenticated first-token run pass.
Abstract-memory traces cannot establish physical DDR or PCIe correctness.

After both runs terminate, compare their traces inside the Nix environment:

```sh
python3 scripts/analysis/compare_memory_traces.py reference.trace accelerator-memory.trace
```

Exit 0 means identical, nonempty, balanced ordered transactions; exit 1 reports
the first differing request/response or unequal length; exit 2 reports malformed,
empty or incomplete input. The comparator streams the files without loading
them into RAM. It stops at the first mismatch and does not validate the remaining
suffix. A matching trace is not inference acceptance: independently require both
runs' successful terminal status, full-image checks and authenticated token.
Do not use this comparison to declare acceptance while either trace is growing.
