# Task 3B normal-command dispatch overlay

The files under `third_party/task6-e368449` remain verbatim pinned upstream
inputs. `scripts/pipeline/apply_task6_command_overlay.py` transforms only the
normal-mode loader command boundary, after its existing PCIe-priority/JTAG
source mux. The separate `task6_command_overlay_pins.json` authenticates the
input, output, and new `rtl/diagnostics/task6_normal_command_stage.sv` bytes.

`nix/task6-board-shell.nix` retains the original `sourceClosure` and adds
`commandSourceClosure`; the latter contains the base manifest and a separate
`command-overlay.json`. The original manifest describes original inputs, not
the transformed shell. Reproduce the output by authenticating/materializing
the base and then applying the deterministic overlay. The immutable original
PCIe/UberDDR3 dependencies and the two-lane profile/clock constraints do not
change. This shell adaptation is not compiler-generated accelerator RTL.

The sole new boundary adds one controller-clock cycle from command capture
to sequencer dispatch. Selected payload, event, source identity, accepted or
legacy-restart decision, and opcode/chunk predicates travel in one bundle.
The original phase toggle still advances on every raw event, including busy
events. Eligibility is sampled at capture, never reconsidered when dispatch
occurs: an event arriving while busy stays ignored even if the loader becomes
idle in the next cycle. Invalid magic/readiness preserves the legacy restart
branch, while unsupported opcode/chunk combinations retain `LOADER_ERROR`.
Cold PLL reset clears the bundle; runtime PCIe abort/drain behavior remains
the separately tested existing integration behavior.

This does not add command queueing or a new host handshake. As with the
original shell, senders must respect loader completion; completion follows
the one-cycle-later dispatch. The regression compares real old/new loader
sequencer projections every cycle with the declared one-cycle offset for
transactions issued at idle, plus separate input-cycle busy boundary checks.
It is simulation equivalence for the exercised environment, not an exhaustive
formal proof over arbitrary external DDR/JTAG/PCIe timing.
