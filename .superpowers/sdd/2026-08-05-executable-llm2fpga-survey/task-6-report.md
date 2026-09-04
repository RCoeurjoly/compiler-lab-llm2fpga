# Task 6 report: compatibility-triage remediation

Date: 2026-08-06
Branch: `codex/executable-llm2fpga-survey`

## Result

All eight frozen routes remain `STOPPED` and `INELIGIBLE`; none is a primary
route and none has passed M0–M3. The receipts retain the complete command,
stdout, stderr, and per-command exit-code record. A stopped gate does not
imply a result for later gates.

The remediation changes three classifications from the previous report:

| Route | Evidence-derived first gate | Failure |
|---|---|---|
| R1 | `RTL_GENERATION` | `F_SOURCE_MISSING` |
| R7 | `SOURCE_CLOSURE` | `F_SOURCE_MISSING` |
| R8 | `SOURCE_CLOSURE` | `F_SOURCE_MISSING` |

R2–R6 retain their prior evidence-derived outcomes. The final summary is
generated from the validated manifests.

`run_route(route, budget_hours)` returns a controlled receipt for every frozen
route. For R1, R7, and R8 it loads and validates the persisted observed receipt
instead of re-executing the route commands; `record_route` remains the command
execution entry point.

## Frozen fixture and pass contract

M0 fixes batch size 1 and these exact dimensions:

- int8 matmul: lhs `[1, 16, 64]`, rhs `[64, 64]`, output `[1, 16, 64]`.
- normalization: input/output `[1, 16, 64]`, scale/bias `[64]`.
- activation: input/output `[1, 16, 64]`.
- RoPE: query/key and their outputs `[1, 4, 16, 16]`; positions `[1, 16]`.
- causal softmax: logits/output `[1, 4, 16, 16]`; mask `[1, 1, 16, 16]`.
- KV read/write: writes `[1, 4, 1, 16]`; cache and reads `[1, 4, 16, 16]`.

An M2 pass now requires a persisted, parsed JSON evidence file named by a
successful recorded command. It must use the exact M2 dimensions, show a
hardware-controlled four-token greedy loop, prove persistent KV state, and
contain two identical four-integer token sequences. A boolean-only or
host-controlled claim is rejected. No recorded route contains M2 evidence.

All lint, simulation, synthesis, evidence-file, and generated-RTL anchors are
validated against actual receipt files and command headers. The R1 anchors are
`stderr.log#command-11` (Verilator) and `stderr.log#command-12` (Yosys).

## R1: compiler-lab control

The environment command exited 0. Capture and Linalg builds also exited 0.
The focused smoke suite exited 1 because of the known stale patches-directory
assertion; it is retained as a baseline diagnostic, not classified as `F_ENV`.
The pinned pytest and `py_compile` diagnostics then failed, also as preserved
baseline diagnostics.

The first relevant taxonomy gate is RTL generation: the native-SV derivation
exited 1 after its store-copied export script attempted to run missing
`verify_calyx_f32_constant_bits.py`. The later Verilator and Yosys diagnostics
both exited 1 against the pre-existing hash-pinned RC RTL and are failure
evidence, not passes. The full exit vector is:

```
[0, 0, 0, 0, 1, 0, 2, 1, 1, 0, 1, 1]
```

The receipt separates the execution commit
`83aac269f3b16ee0c261ab2c7075e4654cfee74d` from frozen audit control
`433592c448f8b19a30dd046a1ec726b09a86d892`. Its recorded scoped diff command
exited 0, proving equivalence for tracked compiler-lab files while excluding
`survey/`, `.superpowers/`, and `tests/test_survey_*`.

## R7: TinyTransformer4TS control

Exact source retrieval/check-out command (command 2, exit 0):

```sh
if test -d /tmp/llm2fpga-task6-r7-receipt-source/.git; then git -C /tmp/llm2fpga-task6-r7-receipt-source fetch --quiet origin 3b3e98fabbca7987809c681244076a646af519b9; else git clone --filter=blob:none --no-checkout https://github.com/Edwina1030/TinyTransformer4TS.git /tmp/llm2fpga-task6-r7-receipt-source; fi && git -C /tmp/llm2fpga-task6-r7-receipt-source checkout --detach 3b3e98fabbca7987809c681244076a646af519b9 && git -C /tmp/llm2fpga-task6-r7-receipt-source rev-parse HEAD && git -C /tmp/llm2fpga-task6-r7-receipt-source status --short
```

The checkout printed the required commit. The source-closure check (command 3,
exit 0) derives that `elastic-ai.creator` is pinned only to the mutable
`add-linear-quantization` branch and that the checked-in VHDL templates remain
unrendered. The remote branch lookup exited 0, Python syntax check exited 0,
import exited 1 for missing `sklearn`, and the available-tool GHDL attempt exited
127. These are retained diagnostics; source closure is the first failed gate.

## R8: Cascade fallback control

Exact source retrieval/check-out command (command 2, exit 0):

```sh
if test -d /tmp/llm2fpga-task6-r8-receipt-source/.git; then git -C /tmp/llm2fpga-task6-r8-receipt-source fetch --quiet origin e21dafa4d877c1dc7846f9e0b60c05a995d033eb; else git clone --filter=blob:none --no-checkout https://github.com/JoshuaLandgraf/cascade.git /tmp/llm2fpga-task6-r8-receipt-source; fi && git -C /tmp/llm2fpga-task6-r8-receipt-source checkout --detach e21dafa4d877c1dc7846f9e0b60c05a995d033eb && git -C /tmp/llm2fpga-task6-r8-receipt-source rev-parse HEAD && git -C /tmp/llm2fpga-task6-r8-receipt-source status --short
```

The checkout printed the required commit. The source-closure check (command 3,
exit 0) proves that the checked-in `soc_system.qsys` source exists, but the
DE10 QSF references an absent generated
`soc_system/synthesis/soc_system.qip`. Generating that input requires vendor
Qsys. The bounded CMake check exited 1 because FLEX is unavailable; the generic
Yosys check exited 1 on the selected legacy Verilog syntax. Both are retained
as later diagnostics; causal-LM coverage is not reached.

## Verification

- `python3 survey/scripts/run_compatibility.py --route all --validate` — exit 0.
- `nix develop -c python -m unittest tests.test_survey_compatibility -v` —
  19 passed.
- Combined Task 1–6 suite — 134 passed in 18.511 s.
- `python3 -m py_compile survey/scripts/run_compatibility.py tests/test_survey_compatibility.py` — exit 0.
- `git diff --check` — exit 0.
- The scoped secret-pattern scan returned no matches.

## Follow-up

R1 needs the committed native-SV helper before it can regenerate RTL. R7 needs
an immutable ElasticAI.Creator dependency and rendered VHDL. R8 needs either
the generated QIP hierarchy or a reproducible, replaceable generator path.
