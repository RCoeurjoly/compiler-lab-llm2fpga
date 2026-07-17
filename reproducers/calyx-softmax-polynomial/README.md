# Calyx polynomial exponential candidate

This is a scalar candidate probe for the stabilized Softmax exponential
`1 + x + x²/2 + x³/6 + x⁴/24 + x⁵/120`. It is not yet the complete RC
Softmax lowering and carries no equivalence claim. Its purpose is to test
whether a standard `arith`-only polynomial form can pass CIRCT's Calyx route.
