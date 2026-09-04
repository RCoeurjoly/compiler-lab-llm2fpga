# Exact f64 floor-to-i64 contract

## Authorized rewrite

`llm2fpga-lower-exact-math-for-calyx` matches only a scalar `math.floor`
whose result is f64, has exactly one use, and that use is
`arith.fptosi ... : f64 to i64`. It replaces the consumer with:

```mlir
%trunc = arith.fptosi %x : f64 to i64
%trunc_f = arith.sitofp %trunc : i64 to f64
%below = arith.cmpf olt, %x, %trunc_f : f64
%delta = arith.select %below, %c-1_i64, %c0_i64 : i64
%rounded = arith.addi %trunc, %delta : i64
```

The original `math.floor` and its sole i64 consumer are erased. The input is
the original f64 value, so the preceding binary64 `arith.divf` is retained.
No direct integer floor-divide rewrite is introduced.

Standalone f64 floors, f64 floors with two uses, and f64 floors whose
`arith.fptosi` result is i32 are outside this match and remain unchanged.
F64 `math.ceil` and `math.rsqrt` remain unchanged. Existing f32
legalization remains on its original path; the f32 fixture retains its
original fptosi-to-i32 consumer and is not consumed by the f64/i64 match.

## Defined domain and oracle

The original conversion defines the supported domain: finite binary64 `x`
whose `floor(x)` is representable as i64. The independent host oracle checks
the following equation on that domain:

```python
trunc = math.trunc(x)
lowered = trunc - 1 if x < float(trunc) else trunc
expected = math.floor(x)
assert lowered == expected
```

It covers positive/negative fractions, exact integers, signed zero,
`math.nextafter` neighbors, values around `2**52` and `2**53`, and the
representable neighbor below `2**63` plus `-2**63`. NaN, infinities,
`2**63`, and the neighbor below `-2**63` are explicitly reported as outside
the original defined domain rather than given a new conversion contract.

## Reviewed plugin and structural probe

The actual exposed flake attribute is `.#llm2fpgaMlirPasses` (not
`.#mlir-passes`). The verified output was:

```
/nix/store/x8w4grzcb4n6v80v88nnwg539abhahvb-llm2fpga-mlir-passes-0.1.0
```

`lib/LLM2FPGAMLIRPasses.so` SHA-256:

```
ec7aa6d4ad5f33696e9599ad23390209bb705cbea78af6ea759daba8d7c767ac
```

The memory-backed `@main` positive fixture was lowered with the reviewed
plugin, isolated from deliberately retained nonmatching functions, then run
through `circt-opt --lower-scf-to-calyx='top-level-function=main'`. The
nonempty 31,821-byte Calyx artifact contains `calyx.ieee754.fpToInt`,
`calyx.ieee754.intToFp`, and `calyx.ieee754.compare`. This is a bounded
single-fixture structural probe only; it does not authorize full-model Calyx
lowering or any registered-hash changes.
