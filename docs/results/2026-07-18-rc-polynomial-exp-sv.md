# Full V=6 RC nonlinear candidate: Calyx to SV

The tree-backed derivation `tinystories-w8a8-rc-polynomial-exp-sv` completed
successfully after applying the opt-in candidate rewrites to the frozen
PT2E W8A8 flat-SCF artifact:

- fifth-order Taylor candidate for `math.exp`;
- constant-exponent multiplication for `math.fpowi` exponents 0--3;
- rational tanh candidate `x(27+x²)/(27+9x²)`.

The rational tanh candidate preserved the complete frozen PyTorch output
tensor for 64 lexical contexts, with zero differing elements. This is the
numerical candidate gate; it is not a proof of real-valued function equality.

The full RC then lowered through CIRCT to valid Calyx MLIR and through the
pinned Calyx 0.7.1 native backend to SystemVerilog. The generated
`main.sv` is 9,955,404 bytes. Calyx's resource backend reports:

| Quantity | Estimate |
| --- | ---: |
| Internal bits | 5,231 |
| External bits | 62,962 |

The native backend emitted two warnings: data-path inference did not converge
within five iterations, and the `--top=main` pickle may exclude files. They
did not prevent SV generation. These are Calyx/backend provenance warnings,
not equivalence evidence.

This report does not claim PyTorch-versus-SV equivalence, FPGA LUT/FF/BRAM/DSP
mapping, or board execution. Those remain separate gates.
