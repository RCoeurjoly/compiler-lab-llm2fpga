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
of `{"memref.future_view": 1}`. Both evaluator and independent verifier decode
pinned-MLIR string escapes.

Review round 1 then exposed that the line-oriented parser still skipped quoted
operations with SSA results and that the `view|cast|shape|copy` fragment filter
was not a fail-closed class gate. Four parseable RED fixtures were added before
the fix. The focused command ran seven tests and produced seven behavioral
failures:

- both censuses omitted a result-bearing generic `memref.cast`, and the
  evaluator consequently selected `valid_normalized_output` instead of
  `next_compiler_frontier`;
- both censuses omitted the escaped result-bearing `"memref.c\\61st"`;
- both censuses omitted the result-bearing generic form of a custom
  `memref.transpose`, while the prior spelling predicate would also have
  accepted that class;
- both censuses omitted result-bearing `arith.constant`, `arith.addi`, and
  `scf.for` from an otherwise complete generic core fixture.

The minimal fix independently invokes the pinned tool with
`-mlir-print-op-generic` for the input and output, decodes every quoted
operation name independent of result syntax, and computes exactly
`after classes - before classes`. The verifier deterministically recomputes
both generic-print censuses rather than trusting the receipt. The same focused
seven tests are GREEN.

## Causal probe replay

The evaluator invoked the exact pipeline
`builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)`
with the pinned tool and rebuilt plugin. It retained command, exit, stdout,
stderr, output, parse command/streams, input-before/after binding, and elapsed
time at canonical evidence paths.

The mandatory causal order and final captured timings were:

| Sequence | Run | Pass ns | Exit | Parse exit | Result |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | predecessor Task 3 subview | 36,294,292 | 0 | 0 | subview removed; argument flattened |
| 2 | identity-offset live probe | 39,790,314 | 0 | 0 | complete affine proof passed |
| 3 | nonzero-offset/stride live probe | 43,439,156 | 0 | 0 | complete affine proof passed |
| 4 | complete retained c22 input | 2,712,162,821 | 0 | 0 | valid parsed output |

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
`42d682b642b899b10bc0814a7786a5803d69b839148e79bbfdc803425e261f34`,
unchanged from the initial Task 3 capture.

Independent after census:

| Registered class | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `memref.collapse_shape` | 4,682 | 4,672 | -10 |
| `memref.copy` | 3,228 | 1,022 | -2,206 |
| `memref.expand_shape` | 921 | 0 | -921 |
| `memref.reinterpret_cast` | 11,449 | 1 | -11,448 |
| **Total** | **20,280** | **5,695** | **-14,585** |

Canonical generic printing found 33 operation classes and 286,983 operations
before, and 32 classes and 283,816 operations after. The receipt now includes
previously omitted core and terminator classes, including `builtin.module=1`,
`func.return=1`, and `scf.yield=40,862/42,558` before/after. The exact after-only
class set is empty; no partial name predicate remains. The semantic
boundary/access status is `proven`. The closed decision is therefore
`valid_normalized_output`; it does not require or claim a zero residual count.
The canonical receipt has self-hash
`64fa2b94030ce859c1d2a6cc648ea52caeffb3f1038dca7f1c567ccbaf32772c`.

## GREEN and adversarial verification

- Public independent verifier: `PASS`, decision `valid_normalized_output`,
  exact after counts 4,672 / 1,022 / 0 / 1.
- Final Task 3 suite: `Ran 19 tests in 163.488s` — `OK`.
- The suite replays the exact commands/streams/output and rejects canonically
  rehashed mutations of model/input/tool/plugin/baseline identities, pipeline,
  command and evidence paths, stale baseline output, causal order, schemas,
  crossed decision branches, false valid/frontier claims, after census, new
  invalid classes, and every affine coefficient/offset/bound/base role or
  identity used by the two proofs. Parseable cases cover result-bearing
  generic and escaped operation names, custom `memref.transpose`, and exact
  result-bearing/core generic operation counts in both implementations.
- Python compilation and `git diff --check` passed. `nix flake check
  --no-build` completed with all checks passed; only the existing application
  metadata and incompatible-system warnings remain.

## Risks and follow-up boundary

- The valid output still has 5,695 registered blockers. In addition, its full
  operation census includes 4,672 `memref.subview` operations already present
  as a class in the input; no claim is made that the artifact is Calyx-ready.
- The next causal behavior is the paired static strided
  `memref.collapse_shape` composition over an already-supported
  `memref.subview`, not standalone subview or the collateral lone reinterpret.
  Registration is ineligible because the registered blocker total is not
  zero.
- Dynamic, rank-reducing, overflowed, and otherwise unsupported view semantics
  remain outside this extension, as proven by Task 2 controls.
- Calyx, SystemVerilog, resource, timing, and board stages were not invoked.
