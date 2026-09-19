# Pinned Task 6 integration shell

The RTL and constraint script in `task6-e368449/` are verbatim Git blobs from
LLM2FPGA commit `e368449e30d5268433443c7de7a9017e5b9187ee`. They were read with
`git show <commit>:<path>`, not copied from the external working tree.
Do not modify them to integrate diagnostics. The new board wrapper lives in
`rtl/diagnostics/compiler_ddr3_trace_replay_top.sv`.

`scripts/pipeline/task6_board_shell_pins.json` authenticates every consumed
file. PCIe and UberDDR3 sources, board XDC, historical clock script and exact
tool/build derivations are immutable Nix-store inputs. The historical loader
bitstream was matched to the three-cold-start full-image receipt by SHA-256.
The PCIe dependency was historically a dirty-tree snapshot: no clean upstream
commit is claimed for those transformed bytes. Ambient checkouts and `/tmp`
sources are not accepted by the materializer.

The old receipt's build used a 50/200 MHz pre-pack script. The diagnostic uses
the existing pinned two-lane 83.333333/333.333333 MHz script instead. Both are
retained separately; historical transfer success is not timing qualification.

Provenance/licensing is separate from compiler-generated accelerator output.
This closure contains no compiler-generated accelerator. Shell file notices
are retained; PCIe identifies CERN-OHL-P. The selected UberDDR3 revision's
LICENSE and RTL headers identify GPL-3.0 (not AGPL); its LICENSE is included in
the materialized closure. No license reinterpretation is made here.

Build with `nix build --impure .#task6-board-shell-source-closure` or
`nix build --impure .#compiler-ddr3-trace-replay-synthesis-screen`.
These intentionally require the pinned historical store inputs to exist;
they fail rather than substitute an ambient checkout. The standalone
`nix/task6-board-shell.nix` entry point avoids making a full flake snapshot
when storage is constrained. Neither target produces a bitstream.
