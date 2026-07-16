# Frozen RC math.exp blocker packet

## Full-RC observation

The unit under test is the frozen PT2E W8A8 representative core `tinystories-w8a8-rc-study-mask9-vocab6-width2`. Its Direct-Linalg, no-handshake, Calyx attempt is reproducible with:

```sh
nix build .#tinystories-w8a8-rc-working-via-linalg-no-handshake-calyx -L --no-link --print-out-paths
```

The durable command outputs inspected for this packet are:

| Derivation | Store output | Relevant artifact and SHA-256 |
| --- | --- | --- |
| scalar upstream reproducer | `/nix/store/8aqx4ppgx7kriwr5lr7mizcmcqk6lkv7-calyx-math-exp-upstream-reproducer` | `manifest.json` — `f4dcafc7169c850747f6cfb866e056da9fce2294c9bbc2f522ee94ea0ed7364b` |
| RC nonlinear slices | `/nix/store/6wal4yycj9f4jnfi2gagqwsmhxb9gry0-tinystories-w8a8-rc-nonlinear-slices` | `slices.json` — `130c19a9b837c8d2d5010d734704698255e02d9411b7c271b5105cc391b075d2` |
| RC nonlinear frontier | `/nix/store/lnzjy94dmnk1v9hdpzglw0av8ckmjzai-tinystories-w8a8-rc-nonlinear-lowering-frontier` | `result.json` — `2f4c3fada16cb7865a834f301a5de5d72f92266a172432b3b55b9ca33a1c8da6` |
| native float closure | `/nix/store/j5w2x9dncfas241msnqwzvr4f2cpcm9a-calyx-rc-basic-float-bindings-selftest` | `main.sv` — `cdcc59cffc7d3e4a73bb42ad80d04b29faeae54ff32b3387c8af062b7016068e` |
| RC MRC binding report | `/nix/store/jf2x5njb0m3lkxplyjiqlvl9bz8nm7gq-tinystories-w8a8-rc-calyx-hardfloat-bindings` | `report.json` — `7bb253571c88ff6a455710bd9cb506f6899e284f5e78aa990f09b6cf08246f1e` |
| full RC Calyx stage | `/nix/store/iyai9653n3pcp2bww1qkqmlq42jlyfvv-tinystories-w8a8-rc-study-mask9-vocab6-width2-calyx` | `manifest.json` — `2d6ba055e33053a1b307751a481252d9a79996e9592458761121b122b34d00a6`; `lower-scf-to-calyx.log` — `59edbfef6b1d0638515fa6fd6a748aa14fcf827a1bf7a12104373407688f4e12` |
| local paper screen | checked-in result | `2026-07-16-rc-math-exp-paper-screen.json` — `bce88e709c1b2d2993bc23e69969126896463883e7b6f0a05fde867ff13c762c` |

The resulting Calyx manifest records:

- normalized full flat-SCF SHA-256: `73ce838808fe78c545fc477f02943d7de64ec55c73dfe43a0fe19f634a14ab18`;
- lower log SHA-256: `59edbfef6b1d0638515fa6fd6a748aa14fcf827a1bf7a12104373407688f4e12`;
- status: `failed`, stage: `calyx`, exit code: `1`, and diagnostic error: `true`;
- float-frontier status: `has-unsupported-calyx-float-frontier`, with 1,102 float operations and two `math.exp` operations;
- `partial_output_discarded: false`: this preserves diagnostic state, not a usable Calyx design.

The first blocker diagnostic is:

```text
.../flat.scf.mlir:2026:16: error: Unhandled operation during BuildOpGroups()
  %102 = math.exp %101 : f32
```

The scalar counterpart is kept in-tree at [`reproducers/calyx-math-exp/input.mlir`](../../reproducers/calyx-math-exp/input.mlir). Its separate upstream reproducer observes the same diagnostic, but `circt-opt` returns exit code zero and writes partial Calyx text. The reproducer therefore explicitly records `valid_lowering: false`; neither exit status nor partial text is accepted as a successful lowering.

## Operation context

The two full-RC `math.exp` sites are mechanically derived from the frozen Torch-MLIR artifact (SHA-256 `0437be0a227396daaa88b78f7f42335f6a1db21e30538a6e5c5e726fc5490c13`). The generated provenance-fragment implementation is kept in-tree at [`scripts/pipeline/extract_quantized_rc_nonlinear_slices.py`](../../scripts/pipeline/extract_quantized_rc_nonlinear_slices.py); its durable slices manifest has SHA-256 `130c19a9b837c8d2d5010d734704698255e02d9411b7c271b5105cc391b075d2` and names `slices/attention-softmax-0.mlirfrag` and `slices/attention-softmax-1.mlirfrag`.

| Provenance slice | Torch-MLIR source range | Retained external values | Operand/result shape and surrounding constants |
| --- | --- | --- | --- |
| `attention-softmax-0.mlirfrag` | 309–315 | `%227`, `%float1.000000e00`, `%int-1`, `%none`, `%true` | `dequantize %227`: `!torch.vtensor<[1,1,8,8],!torch.qint8>` → `[1,1,8,8] f32`; max at `dim=-1`, `keepdim=true`: `[1,1,8,1] f32`; subtraction uses `1.0`; `exp`: `[1,1,8,8] f32` → same; sum uses `dim=-1`, `keepdim=true`, `none`; division returns `[1,1,8,8] f32` |
| `attention-softmax-1.mlirfrag` | 608–614 | `%525`, `%float1.000000e00`, `%int-1`, `%none`, `%true` | Same dataflow and types with `%525` as the dequantized score tensor |

In flat SCF, the corresponding per-row pattern is `load score`, `load row maximum`, `arith.subf`, `math.exp`, followed by the exponent sum and division. This is the numerically stabilized attention Softmax shape, not an isolated arbitrary exponent call.

The scalar MRC and native Futil closure are not numerical-equivalence evidence.

## Toolchain and library matrix

| Route or library | Ownership | Evidence observed | Result at this frontier |
| --- | --- | --- | --- |
| Direct `--lower-scf-to-calyx` | upstream CIRCT | Full RC and scalar MRC report `math.exp` unhandled during `BuildOpGroups()` | rejected; no valid Calyx artifact |
| `canonicalize` / CSE | upstream MLIR | Transform accepts the scalar/slice form | CIRCT still rejects |
| `convert-math-to-funcs` | upstream MLIR | Transform accepts | CIRCT still rejects the resulting route |
| `convert-math-to-libm` | upstream MLIR | Transform accepts | CIRCT still rejects the resulting route |
| Calyx float Futil library | upstream Calyx 0.7.1 | `addFN`, `compareFN`, `divSqrtFN`, `fpToInt`, and `intToFp` are present | no exponent wrapper was observed |
| HardFloat | upstream library bundled through Calyx | Basic arithmetic/conversion MRC closure succeeds | not an exponent implementation |
| TOSA | upstream representation/dialect | The successful RC route intentionally used Direct-Linalg rather than a TOSA handoff | not evaluated here as a direct `math.exp` hardware lowerer |
| Repository compatibility passes | local repository | Existing helpers cover other compatibility issues | no local pass implements `math.exp` |

The direct nonlinear experiment is recorded in [`2026-07-16-quantized-rc-nonlinear-lowering-frontier.md`](2026-07-16-quantized-rc-nonlinear-lowering-frontier.md). It attempted the named upstream routes above; every `math.exp` route has `oracle_comparison_status: not-run` because no executable transformed candidate exists at the PT2E raw-code boundary.

## Local paper corpus evidence

The local screen is documented in [`2026-07-16-rc-math-exp-fpga-corpus.md`](2026-07-16-rc-math-exp-fpga-corpus.md) and its reproducible metadata result [`2026-07-16-rc-math-exp-paper-screen.json`](2026-07-16-rc-math-exp-paper-screen.json). It screened 50 catalog records, verified 49 PDFs, and read 34 candidates; it retains no PDF source text. The classifications are five direct-implementation rows, seven approximation-or-co-design rows, and 22 context-only rows.

The screen separates three evidence classes:

- **Direct implementation evidence:** AccLLM, Hummingbird, TeLLMe/TeLLMe v2, LoopLynx, and SkipOPU describe FPGA softmax/exponent dataflow or online composition. These establish relevant architectural precedent, not a compiler/library lowerer or a numerical contract for this RC.
- **Approximation or co-design evidence:** HLSTransform, IANUS, BFP softmax work, FAST-Prefill, Design Conductor, and the surveys explicitly point to piecewise, LUT, low-precision, or polynomial/Taylor methods. Such methods change or choose numerical semantics and must be treated as separately proposed candidates.
- **Context only:** the other screened hits do not disclose a relevant exponent implementation for this compiler blocker.

No paper is used here as proof that a PT2E W8A8 operation can be replaced while retaining the RC observables.

## Candidate decision

No candidate is labelled `exact` in this iteration.

- **Direct lowerer/library route:** none observed in this iteration. The architectural papers that implement Softmax through named dataflow compositions are not drop-in MLIR/Calyx primitives, and the upstream toolchain routes all stop before a valid Calyx artifact.
- **Named composition needing semantics review:** AccLLM, Hummingbird, TeLLMe/TeLLMe v2, LoopLynx, and SkipOPU describe such compositions. They are useful design precedent, but none comes with the frozen PT2E W8A8 numerical contract.
- **Approximation or changed semantic contract:** HLSTransform, IANUS, BFP Softmax work, FAST-Prefill, Design Conductor, and the survey-reported LUT/interpolation families. These candidate classes must state their range, representation, and numerical contract before any integration.

A named local candidate is not authorized by this packet. It must be independently reviewed, and four-case smoke conformance is insufficient. A valid SystemVerilog candidate must then pass exhaustive `6^8` RC observable-functional-equivalence: all six logits plus the lowest-index argmax token ID, compared against the frozen PT2E W8A8 oracle. The hardware-oracle gate has not run.

## Next full-RC action

The immediate canonical action is upstream/compiler or hardware-library investigation of `math.exp` with the current frozen RC unchanged. A separate approved approximation investigation is also possible, but it must be recorded as a semantic candidate rather than silently folded into the canonical route. Do not integrate either path until it produces a valid complete-RC artifact suitable for the explicit oracle gate.
