# Recorded YPCB full16 board evidence

`hardware/` and the three files `oracle.json`, `verification.json`, and
`verifier.py` were copied byte-for-byte from the archived Nix result
`compiler-full16-three-sram-board-evidence` of 2026-09-29. They are historical
observations, not new measurements. `hardware/receipt.json` has SHA-256
`bbe28dead359698fe9f88a7d3214d795971ad8733b1682135c4168bab9459e1b`.
Each `*-program.log` is an unmodified programmer log. The original runner and
verifier are preserved to show how the archive was produced and checked; they
contain historical machine-local paths and are not the portable replay entry
point.

From the repository root, run
`nix build .#task4-board-evidence --no-link --print-out-paths` to verify the
recorded JTAG transactions and logs against the committed fixed-point oracle
and the source-rebuilt FPGA configuration. This is an **offline evidence
check**, not FPGA programming. See the
[Task 4 closure](../../../docs/results/2026-10-01-task4-fpga-integration-closure.md)
for the result and limitations.
