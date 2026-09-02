# Exact TinyStories Full-Model Calyx Frontier

## Result

The exact TinyStories 1M full-model Calyx lowering reached the explicit 24h wall-clock boundary without producing a Calyx candidate or model artifact. The result is recorded as a `calyx_scalability_frontier`, not a `compiler_frontier`: there was no compiler diagnostic from CIRCT before the deadline.

Primary command:

```text
/nix/store/b9p48l2nrw1c6zncc6f86jd9nr611x7z-circt-1.144.0g20260331_5dc62fe/bin/circt-opt /nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf/pre-calyx.mlir --lower-scf-to-calyx=top-level-function=main -o /nix/store/2ir0cwyca2b9g3gfxmzwbqmchyvvlsnr-tiny-stories-1m-kev-gpt-exact-calyx-frontier/.candidate.calyx.mlir
```

Authenticated input:

- predecessor package: `/nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`
- `pre-calyx.mlir`: 15,748,461 bytes, SHA-256 `54a7df3fec336c5418d3562441a3f9affe45702eb107b89092bc2f7b53afca31`
- predecessor legality receipt self-hash: `451628dba61ea805b09007e89b2135d00dcd93cf225ed4d6d9625a05a598de30`
- `circt-opt`: SHA-256 `087732aac4608ed45effd1d7a81e032791e40a2a11ffff1a75b7031cb69eb2c7`

Timebox evidence:

- start: 2026-09-01T15:46:46+02:00
- deadline: 2026-09-02T15:46:46+02:00
- final live observation: 2026-09-02T15:47:57+02:00
- `circt-opt` PID 2530919 at final live observation: elapsed `1-00:01:13`, CPU `1-01:55:49`, 107% CPU, RSS 841,240 KB
- high-water RSS from `/proc/2530919/status`: 943,228 KB
- output directory materialized after external SIGTERM with `manifest.json` and a zero-byte `lower-scf-to-calyx.log`
- candidate, model artifact, and partial artifact: not present
- stage manifest after termination: `status: failed`, `exit_code: -15`, `first_diagnostic: "circt-opt exited with status -15"`

The `exit_code: -15` is treated as termination evidence only. It is not a compiler diagnostic and was intentionally kept out of `first_diagnostic` in the final frontier receipt.

## Artifacts

- signed timebox evidence: `artifacts/comparison/tinystories-1m-exact-calyx-timebox-evidence.json`
  - evidence self-hash: `73e9eb6d43cf3945c7e6600adbfaf150ecdaf26c67381ba2ffbd5ee08d25b827`
  - file SHA-256: `3f2e704e76d0b38ad9c11dc5b958fcd322aaebbadf82a3a96501dd7996be4738`
- canonical frontier receipt: `artifacts/comparison/tinystories-1m-exact-calyx-frontier.json`
  - receipt self-hash: `3cfff3b6c854c3632bc05b1e7d307c31a4b2dfdd0125fb6a6e0d9104411606de`
  - file SHA-256: `a690bb8eaaa0570747d5ef9e0c56f1a2594017887d79d658fb36ca455f3e6442`

## Verification

- Focused unit suite: `nix develop -c python -m unittest tests/test_exact_tinystories_calyx_stage.py tests/test_exact_tinystories_calyx_frontier.py -v` passed 34/34 tests.
- Verifier replay regenerated `/tmp/tinystories-calyx-frontier-replay.json` from the signed timebox evidence and predecessor package.
- `cmp artifacts/comparison/tinystories-1m-exact-calyx-frontier.json /tmp/tinystories-calyx-frontier-replay.json` passed byte-for-byte.
- `git diff --check` passed.
- `nix flake check --no-build` passed; Nix reported `all checks passed`.

## Root-cause evidence

The authenticated pre-Calyx input is a single-function, loop-heavy exact model:

- 293,972 lines
- 42,558 `scf.for` lines
- 102,229 `arith.` lines
- 106,621 `memref.` lines
- zero `scf.if`
- zero `linalg.`

Loop-shape analysis supplied during monitoring found that the 42,558 loops normalize to 274 structural forms. The largest repeated forms are vector-add inner loops, i64 multiply/store loops over 1024x16384, i64 multiply/store loops over 256x4096, and select/store loops. Combined with sustained CPU activity at the deadline and no candidate output, this supports a compiler-scaling frontier rather than transport, Nix, or I/O failure.

## Reduction

Bounded reducer work is not applicable to this result. There is no CIRCT compiler diagnostic and no rejected candidate to minimize; the frontier is the 24h scalability boundary itself.

## Next-path guardrails

Do not replace exact model semantics with generic associative/vector reductions. Any future compact path should preserve the exact `serial_gemv_accumulate` contract: ascending input-index signed i64 MAC with two's-complement wrap, followed by per-output Q8.24 scale/rounding and the 97 activation Q/DQ boundaries. A compact pattern must emit traceable GEMV boundary witnesses.

The viable next path is not a CIRCT workaround: isolated `torch.export` can retain a custom exact GEMV boundary as a `torch.operator` in raw Torch-MLIR, but the pinned backend rejects illegal `torch.operator`. A future implementation should use an out-of-tree Torch-MLIR-ABI-matched pre-backend legalizer before the fixed backend pipeline, then preserve the boundary through Linalg/SCF/Calyx as an explicit component/invoke.
