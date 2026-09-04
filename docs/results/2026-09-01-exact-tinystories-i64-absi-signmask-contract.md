# Exact scalar i64 `math.absi` sign-mask contract

The exact pre-Calyx math legalization pass lowers only scalar `math.absi` with
an i64 operand and result. At the original operation location it emits:

```mlir
%shift = arith.constant 63 : i64
%sign = arith.shrsi %input, %shift : i64
%flipped = arith.xori %input, %sign : i64
%result = arith.subi %flipped, %sign : i64
```

No arithmetic overflow flags are attached. For every 64-bit encoding `bits`,
the contract is `sign = -1` when bit 63 is set and zero otherwise, followed by
`((bits ^ sign) - sign) mod 2^64`. This agrees with two's-complement absolute
value, including the wrapped `INT64_MIN` result.

The regression fixture keeps scalar i32 and vector<i64> `math.absi` as negative
controls. Its memory-backed scalar i64 path is lowered through the pinned
SCF-to-Calyx probe and requires `calyx.std_srsh`, `calyx.std_xor`, and
`calyx.std_sub` without a comparator or multiplexer.

## Verified artifact

- Authoritative Nix plugin:
  `/nix/store/wi82k10jk0pscc9ypapvbc1lykkn2sc0-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`
- Measured SHA-256:
  `901fd383935d5af48e616eb881ae1b72408f4cb26dfbef94ea7be3049d61760f`
