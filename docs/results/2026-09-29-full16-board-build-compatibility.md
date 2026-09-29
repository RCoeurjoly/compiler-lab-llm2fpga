# Full16 board synthesis: retained FSM encoding and proven RAM compatibility

The approved full16-only Nix recipe now preserves the compiler's existing
state encoding and converts unsupported RAM64X1S primitives to RAM64X1D.
Compiler-generated RTL, the authenticated model/image and arithmetic, PCIe,
UberDDR3, the two-lane 333/83.33 MHz profile and timing constraints are unchanged.
This is a tool-compatibility change, not an accelerator implementation or RC
substitution. No kev-gpt accelerator RTL is used.

```sh
nix build --impure --offline --no-link .#compiler-full16-ddr3-board-synthesis
nix build --impure --offline --no-link .#compiler-full16-ddr3-fsm-encoding-check
nix build --impure --offline --no-link .#compiler-full16-ddr3-ram64-proof
```

After native process lowering and flattening, the recipe asserts that the
canonical `main/fsm0.out` exists and marks only it `fsm_encoding=none`.
The ordinary complete Xilinx synthesis flow remains in place, including DSP
and memory mapping and platform FSM handling. Protecting its pre-flatten alias
had previously failed; the native regression executes the evaluated production
preparation against the actual compiler checkpoint. It failed before the
change and passes afterward. Legacy synthesis branches are unchanged.

The final package requires both that regression and four native Yosys RAM
proofs: zero and high-entropy initialization, with normal and inverted write
clocks. Each includes initialized SAT base cases and complete-state temporal
induction. A deliberately disabled write enable must produce a native SAT
counterexample, not merely a parser error. These prove the logical primitive
transition contract, not physical timing or DDR calibration.

The conversion preserves INIT, clock polarity, address, data, write enable and
the original output, with the unused second read port addressed identically.
Standard Xilinx library loading/process lowering supplies the new primitive's
port definitions. The real-netlist audit requires the same implementation
module/cell sets and a bijective signal mapping, checks all other cells exactly,
and checks all 64 conversions. Native fault controls reject corrupted INIT,
write enable, address, output and an extra implementation module. The extra
module control initially exposed an audit gap; the corrected audit passes
the real netlist and rejects all five faults. Library blackbox/whitebox
declarations are distinguished from implementation modules.

Historical reset/BAR-observer netlist patches are excluded from full16 paths;
current reset, abort and flush semantics are preserved. This does not authorize
or qualify those historical patches for the current accelerator.

## Immutable results

- Raw synthesis:
  `/nix/store/irw0a85f6pd013raxz6gjs1zjbrspjpr-compiler-ddr3-trace-replay-synthesis-screen`.
  Native Yosys completes in 518.59 seconds, with 1783.06 MB peak memory,
  inside the unchanged 600-second deadline and added 12 GiB virtual-memory cap.
  Final implementation checks report zero problems. Earlier frontend warnings
  are retained, not treated as final qualification failures or silently waived.
- Audited production package:
  `/nix/store/dw8yrrixsiw96m4giz7nzpjz0gq9ycw2-compiler-full16-ddr3-board-compatible-synthesis`.
  It contains the mapped JSON, raw-synthesis link, FSM check, primitive proofs,
  native logs, graph audit and passing five-fault control run.
- Native FSM check:
  `/nix/store/gx5lmw4vrs7mhzlf6jcn43f02287cm4d-compiler-full16-board-fsm-encoding-check`.
- Native RAM proofs:
  `/nix/store/vh0x7gzii2ijhcpqlhscg6dhal3phps5-compiler-full16-ram64-initialized-induction-proof`.

## Physical and verification limits

The separately bounded placement diagnostic for the preceding equivalent
compatibility recipe completed without routing:
`/nix/store/zbbydwv7xvmcb0kix6308plmx3xy4qng-compiler-full16-ddr3-board-placement-diagnostic`.
Its pre-route estimate is **42.04 MHz, failing rowstream's required 83.33 MHz**;
PCIe estimates 71.97 MHz against 62.5 MHz. Its critical rowstream path traverses
the existing DDR command-accept/enable logic, with estimated 22.8 ns interconnect
and 1.0 ns logic delay. This is localization evidence, not a routed timing
report for the final production artifact. Diagnostic `timing-allow-fail` does
not qualify a bitstream or relax constraints.

The repository-wide unittest run with cached Nix-declared Python and native
HDL tools and Nix-daemon access timed out at 180 seconds (exit 124), without a
final suite result. It is not a green suite. Earlier bare-Python/sandbox runs
had missing-tool and daemon-access failures and are not the authoritative
full-suite environment. Raw logs are retained in the execution ledger workspace.

No routing, new bitstream, programming, physical DDR3 inference or multi-token
external-memory acceptance is claimed. The accepted on-chip full16 image and
loader-only baseline remain preserved. Next work must address the evidenced
timing path under unchanged clocks/profile, then qualify routing before board
calibration/BIST, exact-image PCIe loading/readback and accelerator inference.
