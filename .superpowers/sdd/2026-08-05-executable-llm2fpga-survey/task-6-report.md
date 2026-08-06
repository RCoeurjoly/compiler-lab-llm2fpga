# Task 6 report: common compatibility triage

Date: 2026-08-06

Branch: `codex/executable-llm2fpga-survey`

Starting revision: `c678ac19a3c90fed27c5329b2ebb624436693385`

Frozen compiler control revision: `433592c448f8b19a30dd046a1ec726b09a86d892`

## Outcome

The eight frozen route receipts were generated from actual commands and validated. Every route stopped at its first hard gate and is `INELIGIBLE`; no route is `PRIMARY`. No route passed an M0, M1, M2, or M3 compatibility fixture, and no M2 simulation was executed. Successful commands in the receipts are environment, repository-build, hash, API, or static-audit checks only; they are not represented as fixture passes.

Each route directory contains `README.md`, `manifest.json`, executable `commands.sh`, `stdout.log`, and `stderr.log`. `manifest.json` records every command and exit code, and records the SHA-256 digest of `commands.sh`. Failed diagnostics were retained rather than rewritten as successes.

## TDD record

The compatibility contract tests were written before the implementation.

1. Initial RED: `python -m unittest tests.test_survey_compatibility -v` failed with `ModuleNotFoundError: No module named 'survey.scripts.run_compatibility'`.
2. Command-execution test RED: importing `execute_commands` failed before the command runner existed. GREEN records exit codes `[0, 7, 0]` and proves diagnostics continue after failure.
3. Recorded-output tests RED: fixture, summary, and route receipt files did not exist. GREEN validates all eight on-disk receipts and their command hashes.
4. M2 guard RED: a host-controlled claimed M2 pass was accepted. GREEN rejects any M2 pass without the frozen M2 fixture, implemented hardware loop control, persistent KV state, token-identical output, and executable evidence.
5. Route-recording test RED: `record_route` did not exist. GREEN executes the frozen R3 audit commands and records the real `matching_artifact_rows=0` result.
6. Receipt-integrity test RED: a command-result row naming a different command was accepted. GREEN requires every result to preserve the exact command, one-based index, and integer exit code, and requires `commands.sh` to reconstruct exactly from `executed_commands`.

The final focused suite has 12 tests. The combined Task 1 through Task 6 suite has 127 tests.

## Frozen fixtures

- M0: batch 1, static operator shapes for int8 matmul, normalization, activation, RoPE, causal softmax, and KV read/write. Integer output must be identical; fixed-point tolerance is one LSB; floating tolerance is `1e-5` absolute and `1e-4` relative.
- M1: one block, model width 64, four heads, FFN width 128, sequence 16, batch 1, with the same numerical rules.
- M2: two blocks, model width 128, four heads, FFN width 256, vocabulary 256, maximum sequence 32, batch 1, and four-token greedy decode. KV state must persist across decode steps and token IDs must be identical.
- M3: the frozen compiler-lab TinyStories repository fixture, batch 1, with identical integer output against the frozen PT2E W8A8 evaluator.

The framework accepts only the protocol failure codes, enforces the frozen 16/40-hour budgets, rejects a failed hard gate marked `PRIMARY`, and rejects unsupported M2 pass claims. All recorded `m2_evidence` mappings are empty because no M2 attempt was reached.

## Route results

### R1 — compiler-lab MLIR/CIRCT control

- First hard gate: `SMOKE_TESTS`
- Result: `STOPPED`, `INELIGIBLE`, `F_ENV`
- Source revision: `433592c448f8b19a30dd046a1ec726b09a86d892`
- Command exits: `[0, 0, 0, 1, 0, 2, 1, 1, 0, 1, 1]`
- The TinyStories capture derivation and Linalg lowering derivation built successfully.
- The focused baseline smoke suite passed 18 of 19 tests. The preserved failure is `test_unused_patch_stacks_are_archived_not_active`, whose stale assertion expects `patches/` not to exist.
- Pinned pytest 8.1.1 under Python 3.11 stopped collection with seven `paperlib` submodule import errors and the known `tests/test_rc_observable_driver.py` f-string `SyntaxError: f-string expression part cannot include a backslash`. The separate `py_compile` command reproduced that syntax failure.
- The current representative-core native-SV derivation stopped because its store-copied export script tried to run nonexistent `/nix/store/verify_calyx_f32_constant_bits.py`. Inspection identified the omitted `CALYX_VERIFY_F32_CONSTANT_BITS` derivation input, but Task 6 preserved the baseline and made no compiler repair.
- A pre-existing, hash-pinned RC RTL file was audited at `/nix/store/b8pwl1r7jq05hn5pphj4zxyg67c3zxjs-xv720lfw0g2mywl7lksp66f81gwamaha-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv/sv/main.sv`: 9,955,404 bytes, SHA-256 `f0e0f500a44ef2daabecd780d743fee2585a46593c2e3d67a7e6b189fd28f983`.
- Verilator lint failed with too many preprocessor tokens on one line. Generic Yosys synthesis failed at line 727 with `unexpected TOK_DEFAULT`. These logs are failure evidence, not lint or synthesis passes.
- No compatibility fixture gate passed. An auxiliary native-SV derivation that produced no further output for several minutes was terminated after the hard gate was already established; it is not claimed as evidence.

### R2 — FlightLLM parameterized RTL artifact

- First hard gate: `SOURCE_CLOSURE`
- Result: `STOPPED`, `INELIGIBLE`, `F_VENDOR_IP`
- Artifact: Zenodo record 10462167 version 1.0.5
- The 1,269-byte licensed README was retrieved. It explicitly states that the RTL is Infinigence-AI IP and that the deposit supplies a pre-generated U280 bitstream, precompiled cases, and host code instead of open-source Verilog.
- The cached Zenodo record lists a 6,409,565,790-byte implementation archive; it was not downloaded because the README already proves that independent RTL lint and synthesis cannot be performed.
- README SHA-256: `efd1d505ecb353f8c7f3e16b75d1fdd43e962cc33ec0160668bbc5ab0921d8f8`; record-response SHA-256: `e33b129691e81eabfe10496d7486bfdb2e6d5977fc1d2f6f4a3fa0cd36270df3`.

### R3 — Mase compiler route

- First hard gate: `SOURCE_PIN`
- Result: `STOPPED`, `INELIGIBLE`, `F_SOURCE_MISSING`
- The frozen Task 5 artifact inventory has zero paper-attributed Mase artifact rows. No generic checkout was substituted.

### R4 — Allo MLIR/HLS route

- First hard gate: `SOURCE_CLOSURE`
- Result: `STOPPED`, `INELIGIBLE`, `F_SOURCE_MISSING`
- General Allo source is audited at Apache-2.0 commit `74b0373ecbc4cfded24f5660c12eee4253c31be5`, audit-tree SHA-256 `f9f59fd6e68f950b1333719c872682a188295b5f89a016383509c00b43366608`.
- The selected paper records the LLM artifact as a future release. The general Allo tree is not a substitute for complete paper-specific LLM source or RTL.

### R5 — FINN transformer-adjacent route

- First hard gate: `ARTIFACT_ATTRIBUTION`
- Result: `STOPPED`, `INELIGIBLE`, `F_SOURCE_MISSING`
- The frozen artifact inventory has zero attributed FINN rows. Generic FINN was not substituted.

### R6 — hls4ml transformer route

- First hard gate: `ARTIFACT_ATTRIBUTION`
- Result: `STOPPED`, `INELIGIBLE`, `F_SOURCE_MISSING`
- The selected paper audit explicitly records no attributed public project artifact for the transformer extension. Its paper PDF SHA-256 is `52e6be2898b331cb37bedb6745dfacb094e9c3792f73de512b9722d557b6b2b0`. Generic hls4ml was not substituted.

### R7 — open reusable accelerator control

- First hard gate: `CAUSAL_LM_COVERAGE`
- Result: `STOPPED`, `INELIGIBLE`, `F_INTERFACE`
- The MIT-licensed TinyTransformer4TS source is audited at commit `3b3e98fabbca7987809c681244076a646af519b9`, tree-response SHA-256 `09db867d6000c8f0d8ee8868696d7981e66ca0665762ed86c27df34bd7fe796b`, with 17 RTL files.
- It implements a non-causal time-series encoder and has no causal-LM prefill, autoregressive decode, persistent KV cache, or token-generation interface. Source availability therefore does not make it M2-viable.

### R8 — Cascade CPU/FPGA fallback control

- First hard gate: `CAUSAL_LM_COVERAGE`
- Result: `STOPPED`, `INELIGIBLE`, `F_INTERFACE`
- Cascade is audited at commit `e21dafa4d877c1dc7846f9e0b60c05a995d033eb`, tree-response SHA-256 `5b3101bd5b9edfc09d115057f560b04cdecf886822f20ed4cbac3d322be41ef0`.
- The cached GitHub API reports `NOASSERTION`, while the inspected license text is BSD-2-Clause; this route was not incorrectly rejected as `F_LICENSE`.
- Cascade is a Verilog virtualization control, not a causal-LM implementation, and provides no prefill, autoregressive decode, token loop, or persistent KV cache.

## Receipt integrity

The route manifest and command-file hashes at final validation were:

| Route | `manifest.json` SHA-256 | `commands.sh` SHA-256 |
|---|---|---|
| R1 | `0e2d7ea2e73eedee0f6cf58b3dc92b9b1516a83cf2ff2f8272cb6f70bbd7b51e` | `4be840475a00e1ff70b0d1674112d8bebcefb96d6de49dd94141fcb57d04e9f0` |
| R2 | `885e6ee4d2c3fc42b8380a657cfe75b2490afca17151b6ca66d9dd7d2dc41a8b` | `53910a84bccf114590382ae7597b818200f4106077e69d7d69e48f91520c389c` |
| R3 | `9a7e1009a50a6ba9554cd695d22d424bc19e2e5945244c916a9d73bb1a6a3ebe` | `83a92dc95ac9035ace6e378625ecede2227f0ed8ebef9c6297f4aff3ade853fd` |
| R4 | `889ec44023c8e6a5600caf3b85d64204a64cef2aaa4a3e3399754eabb7c0e77a` | `4ab90d191390be155cfdc8d65dd98fe2e92f34d177942f77f137d4d17961df74` |
| R5 | `ed73fe0c58e7e27e8fe8a54834a43f5dda3ebf4fc9cdc059780e046eaba48eba` | `6693f990c87c963abf1f3415538567d59d02b14abcc1db1c399fd8202b447be1` |
| R6 | `61d02407c5fea4f83ddb408723fba70592fbde90f0def227171f7080cd5c9fe2` | `253ff3d97df1643c5618cf4a91dfe02bc172c4ca223dc24c1f55171b8b73d480` |
| R7 | `27c5126d46d776d7a81170f9654c1fd88a8b3f9a8f86fd2d70e7f4e94a624652` | `3a6b12ca8ac85c6dda6101bd768bb2ef058e20cafd19990decce137dc12e5ffc` |
| R8 | `5cbfe7b526fd9558783bfac05519ca6396ee6a633067e002a15e05f9636e1c21` | `f0d4c8a080ed9da423320b5522c6ddaabc8326a5a7e3da8844dc31d36f9001ba` |

Additional output hashes: fixtures `0692e1e2093f1b681db6af790a153ec19bee910a57e6a1f445478e9066ca4a7e`; summary `eefe10fb429dc3df53f6be88cb95adc9bf76c5f380196e767bf173026163210f`.

## Verification

- Focused: `nix develop -c python -m unittest tests.test_survey_compatibility -v` — 12 passed in 0.041 seconds.
- Combined Task 1–6: `nix develop -c python -m unittest tests.test_survey_scope tests.test_survey_phase1 tests.test_survey_screening tests.test_survey_selection tests.test_survey_artifacts tests.test_survey_compatibility -v` — 127 passed in 12.353 seconds.
- Receipt validator: `python3 survey/scripts/run_compatibility.py --route all --validate` — exit 0.
- Syntax: `python3 -m py_compile survey/scripts/run_compatibility.py tests/test_survey_compatibility.py` — exit 0.
- Integrity audit: all eight command hashes match, every command/result pair aligns, every receipt is `STOPPED/INELIGIBLE`, and no receipt contains simulation or M2-pass evidence.
- `git diff --check` — exit 0.
- Secret-pattern scan across Task 6 code and evidence — no matches.

## Preserved concerns and bounded follow-up

1. R1 cannot become eligible until a separate compiler-lab change repairs the frozen Python 3.11 collection issue and supplies `CALYX_VERIFY_F32_CONSTANT_BITS` to the native-SV derivation, followed by fresh RTL generation, lint, and synthesis.
2. R2 requires redistributable source RTL from the IP owner; the closed bitstream cannot satisfy independent verification.
3. R3 through R6 require exact paper-attributed, immutable source releases. Generic upstream projects cannot fill the evidence gap.
4. R7 and R8 need causal-LM prefill/decode, a hardware token loop, and persistent KV semantics before M2 can be attempted.
5. The stored R1 RTL is evidence from an existing hash-pinned derivation and failed both independent lint and synthesis. It is not evidence that the current native-SV route generated usable RTL.

## Commits

The scoped compatibility implementation and evidence commit is `21ad3e6f27f6bb239ecee519a9362951dd19b77c` (`survey: record route compatibility triage`). This report is committed separately so it can cite that immutable implementation commit without a self-referential hash.
