# Task 2 Report: Exact TinyStories Calyx Frontier

## Status

Task 2 completed as a deterministic 24h Calyx scalability frontier. The exact full-model `--lower-scf-to-calyx=top-level-function=main` run did not produce a candidate or compiler diagnostic before the explicit wall-clock deadline.

The final receipt is intentionally not `compiler_frontier`. The only terminal condition was external SIGTERM after the 24h timebox, so the final canonical receipt is `calyx_scalability_frontier` with `first_diagnostic: null` and `replay: null`.

## Process timeline

- 2026-09-01T15:46:46+02:00: inherited primary build start.
- 2026-09-02T10:10:17+02:00: recovery resumed in `/home/roland/compiler-lab-llm2fpga/.worktrees/exact-tinystories-compiler` on branch `codex/exact-tinystories-compiler`.
- 2026-09-02T15:46:46+02:00: explicit 24h deadline.
- 2026-09-02T15:46:57+02:00: full PID/command identity was rechecked after the deadline; `nix` PID 2530843, runner PID 2530918, and `circt-opt` PID 2530919 were still live on the exact authenticated command.
- 2026-09-02T15:47:57+02:00: last live post-deadline snapshot before blocked agent-side termination: `circt-opt` PID 2530919 elapsed `1-00:01:13`, CPU `1-01:55:49`, 107% CPU, RSS 841,240 KB.
- 2026-09-02T18:24:13+02:00: recovery observed the process tree gone after user-side termination. The `result` symlink resolved to `/nix/store/2ir0cwyca2b9g3gfxmzwbqmchyvvlsnr-tiny-stories-1m-kev-gpt-exact-calyx-frontier`.

## Authenticated command and inputs

Primary command:

```text
/nix/store/b9p48l2nrw1c6zncc6f86jd9nr611x7z-circt-1.144.0g20260331_5dc62fe/bin/circt-opt /nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf/pre-calyx.mlir --lower-scf-to-calyx=top-level-function=main -o /nix/store/2ir0cwyca2b9g3gfxmzwbqmchyvvlsnr-tiny-stories-1m-kev-gpt-exact-calyx-frontier/.candidate.calyx.mlir
```

- predecessor package: `/nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf`
- `pre-calyx.mlir`: 15,748,461 bytes, 293,972 lines, SHA-256 `54a7df3fec336c5418d3562441a3f9affe45702eb107b89092bc2f7b53afca31`
- predecessor legality receipt self-hash: `451628dba61ea805b09007e89b2135d00dcd93cf225ed4d6d9625a05a598de30`
- `circt-opt`: `/nix/store/b9p48l2nrw1c6zncc6f86jd9nr611x7z-circt-1.144.0g20260331_5dc62fe/bin/circt-opt`, SHA-256 `087732aac4608ed45effd1d7a81e032791e40a2a11ffff1a75b7031cb69eb2c7`

## Timebox evidence

Final pre-termination state:

- `nix` PID 2530843: elapsed `1-00:01:14`, RSS 38,260 KB
- runner PID 2530918: elapsed `1-00:01:13`, RSS 19,628 KB
- `circt-opt` PID 2530919: elapsed `1-00:01:13`, CPU `1-01:55:49`, 107% CPU, RSS 841,240 KB
- `/proc/2530919/status`: 5 threads, no tracer, no swap, VmHWM 943,228 KB
- `/proc/2530919/io`: permission denied
- output directory, candidate, model artifact, and manifest were not visible at the pre-termination check

Post-termination materialized store:

- output package: `/nix/store/2ir0cwyca2b9g3gfxmzwbqmchyvvlsnr-tiny-stories-1m-kev-gpt-exact-calyx-frontier`
- files: `manifest.json` and zero-byte `lower-scf-to-calyx.log`
- no `.candidate.calyx.mlir`, `model.calyx.mlir`, or `partial.calyx.mlir`
- stage manifest: `status: failed`, `exit_code: -15`, `first_diagnostic: "circt-opt exited with status -15"`

`exit_code: -15` is bound as SIGTERM evidence. It is not treated as a CIRCT compiler diagnostic.

## Artifacts

- `artifacts/comparison/tinystories-1m-exact-calyx-timebox-evidence.json`
  - schema: `tinystories-1m-exact-calyx-timebox-evidence-v1`
  - status: `terminated_at_deadline`
  - self-hash: `73e9eb6d43cf3945c7e6600adbfaf150ecdaf26c67381ba2ffbd5ee08d25b827`
  - file SHA-256: `3f2e704e76d0b38ad9c11dc5b958fcd322aaebbadf82a3a96501dd7996be4738`
- `artifacts/comparison/tinystories-1m-exact-calyx-frontier.json`
  - schema: `tinystories-1m-exact-calyx-scalability-frontier-v1`
  - status: `calyx_scalability_frontier`
  - frontier: `calyx_scalability_frontier`
  - self-hash: `3cfff3b6c854c3632bc05b1e7d307c31a4b2dfdd0125fb6a6e0d9104411606de`
  - file SHA-256: `a690bb8eaaa0570747d5ef9e0c56f1a2594017887d79d658fb36ca455f3e6442`

## Verifier/test work recovered

- `scripts/pipeline/verify_exact_tinystories_calyx_frontier.py` authenticates the predecessor exact normalized flat-SCF package, validates normal Calyx-stage receipts, independently replays valid compiler-success/compiler-diagnostic bundles, and emits canonical self-hashed receipts.
- The same verifier now has a separate signed-evidence path for `calyx_scalability_frontier` so a 24h deadline termination cannot be misclassified as a compiler diagnostic.
- `tests/test_exact_tinystories_calyx_frontier.py` includes mutation coverage for provenance, forged manifests, valid Calyx artifact acceptance, minimization sidecars, timebox command/input/no-output/termination binding, and external-user SIGTERM observation.

## Root-cause evidence

The authenticated input is a single-function exact model with 42,558 `scf.for` lines, 102,229 `arith.` lines, 106,621 `memref.` lines, zero `scf.if`, and zero `linalg.`. Loop-shape analysis supplied during recovery found those loops normalize to 274 structural forms, dominated by repeated vector-add, i64 multiply/store, and select/store patterns.

At the deadline `circt-opt` was still CPU-active with bounded memory and no candidate output. That pattern supports a compiler-scaling frontier, not a transport, Nix, or I/O failure.

## Reduction

Bounded reduction is not applicable. No CIRCT compiler diagnostic was produced before the deadline and no rejected candidate exists to minimize.

## Verification

- `nix develop -c python -m unittest tests/test_exact_tinystories_calyx_stage.py tests/test_exact_tinystories_calyx_frontier.py -v`: 34 tests passed.
- `nix develop -c python scripts/pipeline/verify_exact_tinystories_calyx_frontier.py --timebox-evidence artifacts/comparison/tinystories-1m-exact-calyx-timebox-evidence.json --predecessor /nix/store/c10d1w5amnb82m695zrdgbclfzkdy3wy-tiny-stories-1m-kev-gpt-exact-normalized-flat-scf --output /tmp/tinystories-calyx-frontier-replay.json`: passed.
- `cmp artifacts/comparison/tinystories-1m-exact-calyx-frontier.json /tmp/tinystories-calyx-frontier-replay.json`: passed byte-for-byte.
- `git diff --check`: passed.
- `nix flake check --no-build`: passed; Nix reported `all checks passed`.

## Next-path constraints

- Do not change the CIRCT path as part of Task 2.
- Any future compact lowering must preserve exact `serial_gemv_accumulate`: ascending input-index signed i64 MAC with two's-complement wrap, followed by per-output Q8.24 scale/rounding and the 97 activation Q/DQ boundaries.
- Isolated `torch.export` and raw Torch-MLIR can retain a custom exact GEMV `torch.operator`, but pinned Torch-MLIR currently rejects it as illegal in the fixed backend pipeline. The viable next path is an out-of-tree Torch-MLIR-ABI-matched pre-backend legalizer that preserves the boundary through Linalg/SCF/Calyx as an explicit component/invoke.
