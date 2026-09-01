# Task 1 report — exact scalar-f32 NegF sign-bit frontier

## RED

- Independent bit-pattern oracle: PASS for signed zeros, normals,
  subnormals, infinities, quiet/signaling NaN payloads, and 128 deterministic
  random encodings.
- Baseline real-plugin integration: expected failure because
  `llm2fpga-lower-negf-for-calyx` was unregistered.
- Bounded CIRCT test: expected failure until the intentionally retained
  f64/vector controls were made private and removed only for the `@main` probe
  with `symbol-dce`.

## GREEN

- `nix build .#llm2fpgaMlirPasses -L`: PASS.
- Focused unit suite: 12 tests, PASS.
- Authoritative plugin:
  `/nix/store/jya09x969y9h6pkjlc1l613pglw2z7if-llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so`.
- SHA-256: `da138b78750abcdcc7f5f467d0991b1e2eb9cf04708186a6b4f0dd8e14df2c6e`.

## Probe

The tmpfs-only, memory-backed `@main` probe produced 405-byte lowered MLIR
and 2,909-byte Calyx IR. It has two f32/i32 bitcasts, one `arith.xori` using
`-2147483648 : i32`, and one `calyx.std_xor`. It has no `arith.negf`, floating
add/sub primitive, or floating add/sub control path.

## Concerns

The pass deliberately does not match f64 or vector NegF. This task makes no
full-model Calyx/SV/synthesis/board claim and does not change pipelines or
authority hashes.
