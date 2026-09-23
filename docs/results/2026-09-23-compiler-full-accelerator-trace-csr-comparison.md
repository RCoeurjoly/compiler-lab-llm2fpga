# Full compiler accelerator timing comparison

This diagnostic compares the current compiler-generated TinyStories-1M
PCIe/UberDDR3 implementation with the existing trace-CSR-elided production
variants. It uses the same XC7K480T target, seed 15, and two-lane 333/83.33
DDR3 profile. It is a placement/timing comparison only; none of these runs
produced an acceptance FASM or hardware inference result.

The current registered-boundary variant measured 37.09 MHz on `rowstream_clk`
and 40.88 MHz on `pcie_user_clk`; the worst PCIe-to-rowstream delay was
19.42 ns. With diagnostic trace CSR logic elided, the existing no-TMDRIV
variant measured 39.86/55.76 MHz and 5.86 ns, while the LUTRAM variant measured
39.22/65.79 MHz and 6.58 ns (rowstream/PCIe and PCIe-to-rowstream delay).

This is useful localization evidence: diagnostic CSR logic is a major part of
the PCIe-side path, but removing it does not recover the required 83.33 MHz
rowstream clock. The remaining blocker is in the compiler/DDR-side logic or
its placement, not merely the trace observer. No speculative RTL change is
made from this comparison; the next change must target an evidenced
compiler-to-DDR critical path and preserve the exact external-memory protocol.

The machine-readable receipt is
`artifacts/diagnostics/2026-09-23-compiler-full-accelerator-trace-csr-comparison.json`.
