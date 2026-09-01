# Exact scalar-f32 NegF sign-bit contract

`llm2fpga-lower-negf-for-calyx` lowers only scalar `arith.negf : f32` to:

```mlir
%bits = arith.bitcast %x : f32 to i32
%mask = arith.constant -2147483648 : i32
%flipped = arith.xori %bits, %mask : i32
%result = arith.bitcast %flipped : i32 to f32
```

Toggling bit 31 is exact for every binary32 encoding. It preserves signed
zeros, normals, subnormals, infinities, and every NaN payload/signaling bit;
only the NaN sign bit changes. Scalar f64 and vector f32 NegF remain outside
this pass's match boundary.

## RED and GREEN

The initial RED ran the independent oracle and real baseline plugin. The oracle
tests passed, while the plugin integration test failed with the requested pass
unregistered; the static registration test also failed. The bounded-CIRCT RED
then showed that retained f64/vector negative controls must be isolated before
the scalar `@main` probe. Marking those controls private and using MLIR
`symbol-dce` isolates only `@main` without changing their pass-boundary test.

GREEN used the authoritative Nix build and ran:

```sh
nix develop -c python -m unittest \
  tests/test_f32_negf_signbit_semantics.py \
  tests/test_calyx_math_legalization.py -v
```

All 12 tests passed. The independent oracle covers positive/negative zero,
normal and subnormal encodings, infinities, quiet/signaling NaN payloads, and
128 deterministic random 32-bit patterns.

## Reviewed plugin and bounded structural probe

The required build succeeded:

```sh
nix build .#llm2fpgaMlirPasses -L
```

- output: `/nix/store/jya09x969y9h6pkjlc1l613pglw2z7if-llm2fpga-mlir-passes-0.1.0`
- plugin: `/nix/store/jya09x969y9h6pkjlc1l613pglw2z7if-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`
- plugin bytes: `21,738,400`
- plugin SHA-256: `da138b78750abcdcc7f5f467d0991b1e2eb9cf04708186a6b4f0dd8e14df2c6e`

The memory-backed scalar `@main` was lowered with the pass plus `symbol-dce`,
then processed with `circt-opt --lower-scf-to-calyx='top-level-function=main'`
in tmpfs. The lowered MLIR was 405 bytes and contains two `arith.bitcast`
operations, one `arith.xori`, and the `-2147483648 : i32` mask. The nonempty
2,909-byte Calyx output contains exactly one `calyx.std_xor`; it contains no
`arith.negf`, `calyx.ieee754.add`, or `calyx.ieee754.sub`. Consequently this
probe adds no floating adder/subtractor or associated floating control path.

This is fixture-only evidence. It does not run or authorize a full-model
Calyx, SV, synthesis, or board flow.

## Concerns

The contract is intentionally narrow: tensor/vector NegF, f64 NegF, and every
other operation remain untouched. Follow-on pipeline wiring and authority
rotation are separate work; this task does not modify them.
