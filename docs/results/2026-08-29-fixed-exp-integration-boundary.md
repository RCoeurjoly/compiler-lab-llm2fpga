# Fixed exponential integration boundary

The kev-gpt reference contract already has an exact compiler-visible table:
4096 unsigned Q1.20 entries encoding `round(exp((index - 4096) / 256) *
2^20)`, with delta clamping at -4096 and a special exact-one value for
non-negative deltas.  The RTL implementation consumes this table inside the
tensor-level attention softmax scheduler.

The remaining compiler work is therefore not a better scalar polynomial.  It
requires a graph rewrite that recognizes the complete attention score row and
lowers the row to the authenticated tensor softmax ABI (including causal
masking, LUT indexing, denominator width, and probability rounding).  A
scalar `math.exp` replacement cannot preserve this contract and is retained
only for resource scouting.
