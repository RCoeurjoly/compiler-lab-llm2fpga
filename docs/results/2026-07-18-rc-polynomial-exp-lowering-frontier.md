# V=6 RC polynomial-exp lowering frontier

The dedicated derivation
`tinystories-w8a8-rc-polynomial-exp-calyx` applies two opt-in candidate
rewrites to the frozen flat-SCF artifact:

1. `math.exp` becomes a fifth-order Taylor candidate.
2. constant `math.fpowi` exponents 0--3 become floating-point multiplies or
   a constant one.

This is not the canonical pipeline and does not change the frozen PyTorch
oracle. It is a lowering experiment only.

The derivation compiled the MLIR plugin and ran the complete V=6 RC through
the pre-Calyx route. `math.exp` and the constant `math.fpowi` blocker were
removed. CIRCT/Calyx then stopped at two `math.tanh` operations. The produced
manifest is therefore `status: failed`; no Calyx artifact, SV, equivalence,
or resource result is claimed.

This is a genuine frontier advance: the failure moved from `math.exp` to the
next nonlinear family. The next candidate must characterize the tanh/GELU
domain and validate an approximation against the frozen PyTorch final-logit
oracle before it can be accepted.
