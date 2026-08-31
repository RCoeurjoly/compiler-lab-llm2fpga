# Task 3 implementer report: authenticated full static-subview replay

## Scope and base

- Assigned base and worktree start: `3e3441a3eddaf912ccd858b605d0b4bd990852c7`.
- Task 1 schema closure: `edd4acb69beb9c7242722f323a96422fd40b8399`.
- Task 2 implementation: `fe1e621d8d892156b8d3fff5cd0f1b96a846eac1`.
- No pass, model, runtime, Nix stage, Calyx, register, RTL, or board file was
  changed. No subagent was used.

## Predecessor authentication

Before the Task 3 test was written, the public Task 2 contract verifier
independently recomputed all 20,280 registered blockers:

- `memref.collapse_shape`: 4,682;
- `memref.copy`: 3,228;
- `memref.expand_shape`: 921;
- `memref.reinterpret_cast`: 11,449.

The public baseline evaluation verifier replayed the prior
`compiler_pass_extension` decision and its exact
`memref.subview` signature
`6149b92a9d179ef65caa53ff8dd33259b3d0c05085e5289384627b80c931f693`.
All 15 Task 2 semantic and fail-closed regressions also passed against the
rebuilt plugin before Task 3 evidence capture.

Immutable identities used by the new receipt:

- model: `tiny-stories-1m-kev-gpt-exact`, with the complete frozen Task 1--3
  identity object inherited from the authenticated contract;
- Task 2 contract file SHA-256:
  `c23de92badac1c72115fda92d70b845acb7991a46181b2fabf6f11612ca43910`;
- Task 3 baseline evaluation file SHA-256:
  `26e0ddcaf0abc6100332378d2cacf0555f3560a7635bcdd60dbb9f47bd5ad0d8`;
- retained c22 flat-SCF input: 18,933,168 bytes, SHA-256
  `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6`;
- pinned `mlir-opt`: 496,904 bytes, SHA-256
  `3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`;
- baseline plugin: 21,714,240 bytes, SHA-256
  `6e6782b5db0255e688f1599c51f6076c3c30514362194ec5eff2632eeb8a6744`;
- rebuilt plugin: 21,720,848 bytes, SHA-256
  `6cc5d3668b066dc7776a511114b47fc77411bc7bb7b6e4ea366d889dd41394f9`.

The rebuilt plugin digest differs from the baseline digest. The pass source is
also byte-bound to blob `8aecb2bdb66cdf179b8517828766e962ffdc6889` at the
assigned base.

## TDD RED

The new behavioral/authentication test was added before either production
script or any receipt/evidence/report existed. The required command discovered
14 tests and failed in five subtests for exactly these absent surfaces:

- evaluator;
- verifier;
- evaluation receipt;
- evidence directory;
- result report.

The remaining 13 tests skipped because their evaluator or evidence dependency
was absent. No production Task 3 file existed during this RED.

A later audit added a separate adversarial RED for a generic escaped operation
name, `"memref.future\\5fview"`. The custom-only census returned `{}` instead
of `{"memref.future_view": 1}`. Both evaluator and independent verifier now
decode pinned-MLIR string escapes and include generic spellings in the new
invalid-class census; the focused test is GREEN.

## Causal probe replay

The evaluator invoked the exact pipeline
`builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`
with the pinned tool and rebuilt plugin. It retained command, exit, stdout,
stderr, output, parse command/streams, input-before/after binding, and elapsed
time at canonical evidence paths.

The mandatory causal order and final captured timings were:

| Sequence | Run | Pass ns | Exit | Parse exit | Result |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | predecessor Task 3 subview | 37,969,076 | 0 | 0 | subview removed; argument flattened |
| 2 | identity-offset live probe | 39,454,203 | 0 | 0 | complete affine proof passed |
| 3 | nonzero-offset/stride live probe | 38,677,640 | 0 | 0 | complete affine proof passed |
| 4 | complete retained c22 input | 2,498,552,923 | 0 | 0 | valid parsed output |

The full input was not executed until the first three results were proven.
Both evaluator and verifier independently reconstructed every symbolic index
expression, variable domain, base argument, load/store role, raw access range,
and linearized access:

- identity case: `offset=0`, coefficients `[64,1]`, hence
  `64*i0+i1` for `i0 in [0,64)`, `i1 in [0,1)`;
- nonzero case: `offset=64`, coefficients `[128,2]`, hence
  `64+128*i0+2*i1` for `i0 in [0,16)`, `i1 in [0,8)`.

Every raw and flattened access range was in bounds. The two post-pass outputs
contain no `memref.subview`.

## Full artifact result and decision

The complete command exited zero with empty stdout/stderr. Its 16,373,009-byte
output parses with the pinned tool and has SHA-256
`42d682b642b899b10bc0814a7786a5803d69b839148e79bbfdc803425e261f34`.

Independent after census:

| Registered class | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `memref.collapse_shape` | 4,682 | 4,672 | -10 |
| `memref.copy` | 3,228 | 1,022 | -2,206 |
| `memref.expand_shape` | 921 | 0 | -921 |
| `memref.reinterpret_cast` | 11,449 | 1 | -11,448 |
| **Total** | **20,280** | **5,695** | **-14,585** |

No newly introduced invalid operation class was found, including custom,
generic, and escaped generic spellings. The semantic boundary/access status is
`proven`. The closed decision is therefore `valid_normalized_output`; it does
not require or claim a zero residual count. The canonical receipt has self-hash
`3c8fbee9e95422c619e5aff1bb8e19e84c90412c1a05e261ba3005bd2826c048`.

## GREEN and adversarial verification

- Public independent verifier: `PASS`, decision `valid_normalized_output`,
  exact after counts 4,672 / 1,022 / 0 / 1.
- Final Task 3 suite: `Ran 15 tests in 155.398s` — `OK`.
- The suite replays the exact commands/streams/output and rejects canonically
  rehashed mutations of model/input/tool/plugin/baseline identities, pipeline,
  command and evidence paths, stale baseline output, causal order, schemas,
  crossed decision branches, false valid/frontier claims, after census, new
  invalid classes, and every affine coefficient/offset/bound/base role or
  identity used by the two proofs.
- Python compilation passed. `git diff --cached --check` passed for every
  authored file; the four exact MLIR stdout artifacts retain their
  receipt-bound trailing blank record and were excluded from that whitespace
  check rather than rewritten.

## Risks and follow-up boundary

- The valid output still has 5,695 registered blockers. In addition, its full
  operation census includes 4,672 `memref.subview` operations already present
  as a class in the input; no claim is made that the artifact is Calyx-ready.
- The follow-up must start from this exact residual census and extend only the
  earliest remaining registered blocker. Registration is ineligible because
  the registered blocker total is not zero.
- Dynamic, rank-reducing, overflowed, and otherwise unsupported view semantics
  remain outside this extension, as proven by Task 2 controls.
- Calyx, SystemVerilog, resource, timing, and board stages were not invoked.
