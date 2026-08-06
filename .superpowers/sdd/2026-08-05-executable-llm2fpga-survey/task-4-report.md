# Task 4 report: deterministic deep-review selection and RQ1–RQ6 extraction

## Status and commit

Task 4 is complete in the isolated `codex/executable-llm2fpga-survey`
worktree. The implementation and frozen extraction are committed as:

- `52ceb27` — `survey: extract deep-review route evidence`

No Task 1/2 receipts, Task 3 decisions, screening classifications, family
relations, or prior generated artifacts were changed.

## Selected count and composition

The generated extraction contains **36 rows**:

- 29 supported Level A project families. The 30 included Level A
  manifestations collapse to 29 families because the TeLLMe family contains
  two included works.
- 6 Level C route-boundary families, one for every frozen executable route:
  `MLIR_CIRCT`, `PARAMETERIZED_RTL`, `HLS`, `DATAFLOW`, `OVERLAY`, and
  `CPU_FPGA_FALLBACK`.
- 1 explicitly required `CONTROL-COMPILER-LAB` artifact-control row, kept
  distinguishable from the 35 corpus project-family rows.

Route composition is:

```text
CPU_FPGA_FALLBACK   6
DATAFLOW           15
HLS                 5
MLIR_CIRCT          2
OVERLAY             6
PARAMETERIZED_RTL   2
```

The `DATAFLOW` count is a documented protocol exception to the 30% cap: the 14
mandatory supported Level A dataflow families alone already exceed 30% of the
36-row sample. The selector enforces the cap for every other route and permits
an exception only when the mandatory supported-Level-A count itself forces it.

The sample also contains four rows selected as paper-reported open-artifact or
compiler-lab controls. Each C representative is explicitly marked as both a
distinct executable route and a conservative route-boundary/incompatibility
case. Those rows do **not** claim an observed build failure: their notes label
the conclusion as inferred from the cited absence of an end-to-end causal token
loop.

## Selection and schema

`score_family()` implements the frozen 0–10 score as:

- `causal_lm_relevance_score`: 0–3
- `distinct_route_score`: 0–2
- `artifact_availability_score`: 0–2
- `open_toolchain_migration_score`: 0–2
- `quantitative_evidence_score`: 0–1

`select_families()` validates the controlled composition, includes mandatory
rows regardless of score, includes score-at-least-7 eligible rows under the
40-row ceiling, applies the route cap, and uses stable ranking by artifact
availability, route distinctness, causal/model relevance, publication year,
and finally lexical `project_family_id`.

The template, manual extraction, and generated CSV use one exact header. Its
metadata and selection fields are:

```text
project_family_id, title, level_final, route_family,
preferred_record_id, publication_year, mandatory_reason,
causal_lm_relevance_score, distinct_route_score,
artifact_availability_score, open_toolchain_migration_score,
quantitative_evidence_score, selection_score
```

The protocol RQ fields are:

```text
RQ1 route:
  rq1_input_frontend, rq1_source_irs, rq1_intermediate_irs, rq1_backend,
  rq1_architecture, rq1_control_model, rq1_generation_mode

RQ2 model coverage:
  rq2_model_family, rq2_prefill, rq2_decode, rq2_token_loop,
  rq2_attention, rq2_ffn, rq2_normalization, rq2_rope, rq2_kv_cache,
  rq2_softmax, rq2_sampling, rq2_completeness

RQ3 reusable components:
  rq3_frontend, rq3_passes, rq3_rtl, rq3_hls, rq3_runtime, rq3_tests,
  rq3_reuse_notes

RQ4 openness:
  rq4_source_openness, rq4_hls_openness, rq4_synthesis_openness,
  rq4_place_and_route_openness, rq4_required_closed_tools_or_ip,
  rq4_vendor_primitives, rq4_migration_work

RQ5 feasibility:
  rq5_minimum_model, rq5_precision, rq5_shape, rq5_memory, rq5_device,
  rq5_resource, rq5_clock, rq5_throughput, rq5_latency, rq5_power

RQ6 verification:
  rq6_reference_model, rq6_vectors, rq6_simulators, rq6_formal_support,
  rq6_environment, rq6_interfaces, rq6_reproduction_status
```

The final fields are `evidence_locations` and `notes`. Strict validation rejects
extra aliases, missing columns, out-of-range or inconsistent scores, duplicate
families, disagreement with frozen family metadata, nonportable evidence, and
any populated decision-critical RQ cell without a matching per-field evidence
entry.

## Evidence method

The extraction uses only sources already available in the frozen corpus and
the pinned compiler-lab repository; no unrecorded online lookup was needed.

- Paper claims use a portable versioned arXiv URL with the exact `#abstract`
  locator. They are limited to information documented in the frozen abstract.
- The compiler-lab control uses GitHub URLs pinned to commit
  `433592c448f8b19a30dd046a1ec726b09a86d892`, exact repository paths, and line
  anchors in `README.md` and the observable-equivalence ADR.
- `evidence_locations` is a JSON object mapping each populated decision-critical
  field to its own locator. All 36 rows have evidence objects; all 201 populated
  RQ cells have a corresponding locator.
- `notes` distinguishes `documented`, `observed`, and `inferred` evidence. The
  six C boundary controls explicitly say that absent token-loop evidence is an
  inference, not an observed incompatibility.
- Unknown values remain empty in CSV. The generated Markdown renders them as
  `not reported`.

Paper-reported source availability is recorded only as a qualified report from
the cited abstract. It does not establish repository contents, license status,
dependency closure, buildability, or reproduction. Those audits remain Task 5.

## TDD RED/green evidence

The initial focused RED run occurred before production code existed:

```text
ModuleNotFoundError: No module named 'survey.scripts.select_deep_review'
Ran 1 test
FAILED (errors=1)
```

After the minimal selector and schema validator were implemented, seven focused
behavior tests were green. Production regeneration then exposed a real edge
case: a mandatory set already equal to the target size returned no selection.
A regression was added first and observed RED with:

```text
ValueError: no 25--40 family selection satisfies the route-family cap
Ran 1 test
FAILED (errors=1)
```

The target-size return was then implemented and the regression turned green.
A second controlled-composition regression was observed RED because omitting
one executable C route did not raise. The selector was then tightened to require
all six C route families, all supported A families, the compiler-lab control,
an open-artifact row, and one route-boundary case per route.

Final focused result:

```text
nix develop -c python -m unittest tests.test_survey_selection -v
Ran 10 tests in 0.560s
OK
```

The focused suite covers score bounds and summation, mandatory A/C/control
inclusion, exact controlled composition, stable lexical ties, the 25–40 range,
the 30% cap and forced Level A exception, the all-mandatory target edge case,
exact schema/evidence validation, and byte-identical regeneration.

Fresh combined survey verification before the implementation commit:

```text
nix develop -c python -m unittest \
  tests.test_survey_selection tests.test_survey_screening \
  tests.test_survey_phase1 tests.test_survey_scope -v
Ran 84 tests in 18.226s
OK
```

`python -m py_compile` completed for the selector and focused tests, and
`git diff --cached --check` exited successfully before commit.

## Reproducibility command

```bash
nix develop -c python survey/scripts/select_deep_review.py \
  --families survey/build/project_families.csv \
  --reviews survey/data/deep_review_manual.csv \
  --out survey/build

nix develop -c python -m unittest tests.test_survey_selection -v
```

Observed generation summary:

```text
selected: 36
routes: CPU_FPGA_FALLBACK=6, DATAFLOW=15, HLS=5, MLIR_CIRCT=2,
        OVERLAY=6, PARAMETERIZED_RTL=2
route_cap_exception: DATAFLOW
```

The committed-regeneration test writes into a temporary directory and compares
both `deep_review.csv` and `deep_review.md` byte-for-byte with the committed
outputs.

## Concerns and limitations

There is no blocking Task 4 concern. The following limitations are explicit:

- This extraction deliberately stops at paper/abstract and pinned local-control
  evidence where precise repository audit evidence is unavailable. Task 5 must
  inspect repositories, commits, licenses, submodules, generated files,
  dependencies, tests, vendor IP, and buildability before any reproducibility
  conclusion.
- The six route-boundary controls characterize missing causal-token-loop
  coverage in the cited evidence. They are not executed failure receipts.
- The `DATAFLOW` cap exception is unavoidable while retaining every supported
  Level A family and is surfaced in both machine output and Markdown.
- The inherited Task 3 single-reviewer limitation remains: the frozen repeat
  sample exists, but no second-reviewer or delayed-repeat agreement statistic
  is invented here.
- Board/part feasibility remains unknown where the paper abstract does not
  report it; blank values are not positive evidence.
