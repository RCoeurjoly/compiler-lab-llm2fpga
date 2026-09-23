# Full compiler accelerator DDR3/PCIe implementation screen

The exact regenerated compiler `main` was integrated with the existing
PCIe/UberDDR3 shell, with `ENABLE_COMPILER_ACCELERATOR=1`, without flattening
the compiler hierarchy. Yosys synthesis completed and the generated netlist
was legalized with the existing RAM64X1S/RAM128X1S compatibility transform.

Seed-15 nextpnr placement reached 122,123 cells, but the implementation is not
qualified:

- rowstream clock: 35.40 MHz achieved vs. 83.33 MHz required;
- PCIe user clock: 32.75 MHz achieved vs. 62.5 MHz required;
- post-placement legalization terminated with `port.net == nullptr`.

This is the first evidence that the full compiler-generated accelerator, rather
than the transport shell, needs an implementation optimization. The PCIe and
UberDDR3 path itself already passed the authenticated hardware trace replay.
No bitstream was produced or programmed for this full accelerator attempt.

An explicitly diagnostic `--force` route with the registered Wishbone boundary
also reached timing analysis, but measured only 43.12 MHz on `rowstream_clk`
and 52.12 MHz on `pcie_user_clk` before the same post-placement legalization
assertion. `--force` therefore is not an acceptance workaround and produced no
FASM. The failure is implementation/toolchain-level; it is not evidence of a
PCIe or DDR3 transaction mismatch.

Flattening the compatible netlist was also tested as a bounded diagnostic. It
preserved the same legalization assertion and reduced the measured clocks to
27.49 MHz (`rowstream_clk`) and 37.03 MHz (`pcie_user_clk`). It produced no
FASM, so the non-flattened compiler hierarchy remains the better measured
variant, although neither variant is currently implementable at the required
frequencies.

The supported `--no-tmdriv` placer diagnostic likewise preserved the
legalization assertion and measured 35.93 MHz rowstream and 37.40 MHz PCIe.
The fixed profile therefore cannot be recovered by a placer-mode switch; the
next implementation step must address the pinned nextpnr legalization/tool
path or a structural implementation change, while retaining the exact
compiler semantics.

## PCIe-meta nextpnr diagnostic

The prior binaries were not interchangeable: the known-good PCIe shell uses
the `openxc7-stable-pcie-meta` source (commit
`32e8b798520d90e1130afe95908f04cf52125cf6` plus its recorded worktree
changes), while the task3 flake's pinned fork lacks the PCIe metadata changes.
Rebuilding the task3 fork, even with the A6 legalization patches, crashed while
importing this netlist before placement. That binary was not used for any
acceptance claim.

As a bounded diagnostic, nextpnr was rebuilt from the known PCIe-meta source
with `0023-disconnect-lut6-a6-before-memory-constant.patch` and
`0024-drop-constant-a6-on-lut5.patch`. Its SHA-256 is
`879f0956df6ff058ceefb9b2390efcab5862a509c556c353698070fcf721168e`.
This run passed post-placement legalization and reached router2, with
42.09 MHz rowstream and 51.40 MHz PCIe user timing, but stopped before FASM
was emitted. It therefore confirms that the earlier assertion is repairable in
the matching PCIe-meta tool path, while leaving the fixed-frequency timing
failure unresolved. No bitstream was programmed.

The task3 flake now points at the published `openxc7-stable-pcie-meta`
revision `32e8b798520d90e1130afe95908f04cf52125cf6` and applies both patches,
so the source/tool distinction is reproducible. The resulting binary has
SHA-256 `4b86f3f971ca0b57d589c0e646dba18439b958f327ee4270d7d67c137e417334`.
The same seed-15 route with this binary again reached the router2 main loop but
terminated before FASM; therefore the next blocker is router completion and
timing/resource closure, not PCIe/DDR3 semantic correctness.

## Production-mode CSR elision

The timing report showed the rowstream critical path traversing the temporary
`replay_bridge.csr` trace register bank. The top and bridge now accept
`ENABLE_TRACE_REPLAY_CSR=0`; that mode keeps the PCIe AXI loader forwarding
path, returns a deterministic DECERR for the diagnostic-only `0x900--0x97f`
window, and ties off replay traffic. The default remains enabled for exact
trace replay, so the accepted replay path is unchanged.

Focused RTL tests pass (`11` tests), and standalone Yosys elaboration/proc/opt
passes with `ENABLE_TRACE_CSR=0`. A full-design synthesis rerun with the
parameter disabled did not complete before the bounded execution ended, so no
resource, timing, netlist, FASM, or hardware claim is made for this mode yet.
