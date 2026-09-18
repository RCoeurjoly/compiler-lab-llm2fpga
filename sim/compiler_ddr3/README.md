# Physical DDR3 simulation gate

The initial `profile` phase elaborates the actual pinned Micron model with a
4-Gbit x16 parameter file and verifies geometry and strict-check settings.
It does **not** exercise initialization, calibration, loading or inference.
The `startup` phase instantiates the pinned controller and PHY, uses production
waits and full BIST geometry, and requires natural calibration/BIST completion.
The runner rejects the not-yet-implemented `load` and `infer` phases.

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
is enforced; `--max-cycles N` additionally bounds controller cycles. Neither a
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
