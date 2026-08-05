# Executable LLM-to-FPGA Survey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the complete, commit-pinned, machine-readable systematic mapping study and artifact-based technical review specified by `~/Downloads/survey_protocol_llm2fpga.md`, including an evidence-supported primary FPGA route and architecturally distinct fallback.

**Architecture:** Keep the study self-contained in `survey/`, with deterministic scripts operating on the pinned paper-catalogue submodule and explicit manual decision files.  Phase 1 converts all source records into normalized work records and controlled A–D/X decisions; subsequent scripts form project families, select deep reviews, collect repository evidence, execute compatibility receipts, and render the report.  The checked-out catalogue commit contains 461 records rather than the protocol's stated 459; preserve all 461 records, record the discrepancy in provenance, and make every count derive from the pinned commit.

**Tech Stack:** Python 3.12 (standard library plus pinned Nix Python packages: pandas, pyarrow, PyYAML, RapidFuzz, Unidecode, requests, requests-cache, tabulate), Nix, Git, local arXiv PDF cache, GitHub/Crossref/OpenAlex/arXiv APIs, PyTorch/Torch-MLIR/CIRCT, Verilator, Yosys, Mermaid, LaTeX.

## Global Constraints

- The source population is the 461-record `LLM-inference-on-FPGA-papers` catalogue at commit `95fd9b9a509f275dd3cfdb3360b33dbcca7429f0`; no record may be silently discarded to reach 459.
- Keep every original record in a lineage table and retain controlled exclusion codes from the supplied protocol.
- Classify bibliographic records, but deep-review project families; a final decision must cite a paper section, repository commit/path, generated log, API response, or reviewer decision.
- Treat a public repository as unlicensed until its pinned licence evidence says otherwise; do not infer reuse permission from visibility.
- Do not call a route FOSS-qualified when it has indispensable proprietary HLS, vendor IP, encrypted modules, or closed implementation tooling.
- Do not call a route end-to-end when it lacks a causal-LM prefill/decode path, persistent KV state, and a deterministic reference comparison.
- Preserve unrelated user modifications, especially `TinyStories/rc_serving_direct_export.py`; survey changes must not alter model/RTL behaviour except through explicitly invoked compatibility commands.
- Track generated evidence required for D2–D16 in Git, excluding only regenerable binary caches and API response payloads whose provenance/index is committed.
- Run mapping and report tests with the declarative survey Python environment; API and compatibility failures must receive an explicit failure code rather than being converted to a passing score.

---

## File and interface map

| Path | Responsibility |
| --- | --- |
| `survey/protocol.md` | Frozen protocol, source hash, and 459→461 snapshot amendment. |
| `survey/config/scope.yaml` | Search vocabulary, levels, route taxonomy, inclusion/exclusion rules, score weights. |
| `survey/data/manual_overrides.csv` | One controlled final decision per source record, including reviewer and evidence location. |
| `survey/data/route_vocabulary.csv` | Canonical route-family IDs, labels, and distinct-fallback grouping. |
| `survey/scripts/common.py` | Record flattening, normalization, identifiers, CSV/Parquet writes, source hashing, command receipts. |
| `survey/scripts/phase1_map.py` | Catalogue normalization, exact/fuzzy deduplication, automatic lanes, and controlled Phase-1 products. |
| `survey/scripts/finalize_screening.py` | Applies overrides, validates one final disposition per record, creates exclusions and project-family inputs. |
| `survey/scripts/select_deep_review.py` | Deterministic family scoring, mandatory inclusions, diversity cap, and selection receipt. |
| `survey/scripts/enrich_metadata.py` | Cached identifier/repository metadata retrieval with request logs and retrieval dates. |
| `survey/scripts/audit_repositories.py` | Pinned repository, licence, source-closure, tooling, and target-platform audit. |
| `survey/scripts/run_compatibility.py` | Uniform route test transcript/receipt writer and failure-taxonomy validator. |
| `survey/scripts/mlir_stage_matrix.py` | Evidence-backed MLIR/CIRCT stage capability matrix and hypothesis results. |
| `survey/scripts/make_figures.py` | Corpus flow, route-family comparison, timeline, and stage-matrix tables. |
| `survey/scripts/build_report.py` | Validates all evidence files and renders Markdown/LaTeX/PDF report. |
| `survey/templates/deep_review.csv` | RQ1–RQ6 family extraction schema. |
| `survey/templates/decision_matrix.csv` | Eight-route hard-gate and weighted-score schema. |
| `survey/build/` | Generated, committed study snapshot and command receipts for D2–D16. |
| `tests/test_survey_*.py` | Offline deterministic contract tests for the survey pipeline and final report. |

## Task 1: Freeze the scope, provenance, and reproducible environment

**Files:**
- Create: `survey/README.md`
- Create: `survey/protocol.md`
- Create: `survey/config/scope.yaml`
- Create: `survey/data/manual_overrides.csv`
- Create: `survey/data/route_vocabulary.csv`
- Create: `survey/scripts/common.py`
- Create: `tests/test_survey_scope.py`
- Modify: `flake.nix`

**Interfaces:**
- `load_scope(path: Path) -> dict[str, object]` rejects missing level definitions, missing controlled exclusions, or score weights not summing to 100.
- `write_provenance(root: Path, output: Path) -> dict[str, object]` records all repository commits/remotes, input SHA-256 hashes, tool versions, UTC timestamp, `expected_records=461`, and `protocol_record_count=459`.
- `surveyPython` is a Nix Python interpreter containing pandas, pyarrow, PyYAML, RapidFuzz, Unidecode, requests, requests-cache, and tabulate.

- [ ] **Step 1: Write scope tests before adding survey files.** Assert that `scope.yaml` contains A, B, C, D, X; every protocol exclusion code; all seven decision-matrix weights; and that the expected count is 461 while the stated protocol count is 459.

```python
def test_scope_records_snapshot_amendment() -> None:
    scope = yaml.safe_load((ROOT / "survey/config/scope.yaml").read_text())
    assert scope["snapshot"]["expected_records"] == 461
    assert scope["snapshot"]["protocol_stated_records"] == 459
    assert set(scope["levels"]) == {"A", "B", "C", "D", "X"}
```

- [ ] **Step 2: Run the scope test and confirm it fails because the survey contract does not exist.**

```bash
nix develop -c python -m unittest tests.test_survey_scope -v
```

- [ ] **Step 3: Add the frozen protocol and scope files.** Preserve the supplied level definitions, inclusion/exclusion criteria, deduplication rules, fixture definitions, hard gates, failure codes, D1–D16 list, and describe why the pinned commit's 461 records supersede the stale count without changing the study question.
- [ ] **Step 4: Add the manual-decision and route-vocabulary headers.** Include immutable `record_id`, `work_id`, `project_family_id`, `level_final`, `include_final`, `exclusion_code`, `route_family`, `reviewer`, `evidence_location`, and `decision_basis` columns; route vocabulary must distinguish `MLIR_CIRCT`, `PARAMETERIZED_RTL`, `HLS`, `DATAFLOW`, `OVERLAY`, and `CPU_FPGA_FALLBACK`.
- [ ] **Step 5: Add the declarative Python environment and `common.py`.** Use source-tree paths, not `~` expansion, in recorded output; atomic writes must include a trailing newline and UTF-8 encoding.
- [ ] **Step 6: Generate `survey/build/provenance.json` and `survey/build/environment_manifest.json`.** Verify compiler-lab, papers, and sibling LLM2FPGA commits/remotes are present and that every catalogue SHA-256 is recorded.
- [ ] **Step 7: Run scope tests and the provenance command twice.** Compare normalized JSON excluding only `generated_at_utc`; the pinned inputs and tool versions must agree.
- [ ] **Step 8: Commit the scope freeze.**

```bash
git add flake.nix survey tests/test_survey_scope.py
git commit -m "survey: freeze corpus and reproducible scope"
```

## Task 2: Normalize all records and implement transparent deduplication

**Files:**
- Create: `survey/scripts/phase1_map.py`
- Create: `tests/test_survey_phase1.py`
- Create: `survey/build/records_normalized.csv`
- Create: `survey/build/duplicate_groups.csv`
- Create: `survey/build/works_deduplicated.csv`
- Create: `survey/build/phase1_mapping.csv`
- Create: `survey/build/phase1_mapping.parquet`
- Create: `survey/build/phase1_uncertain.csv`
- Create: `survey/build/flow_counts.json`

**Interfaces:**
- `extract_records(catalogue: object) -> list[dict[str, object]]` accepts both the current mapping-shaped `papers` catalogue and the list-shaped schema described by the protocol.
- `canonicalize_record(record_key: str, record: dict[str, object]) -> dict[str, object]` emits a stable `record_id`, base arXiv ID, normalized title, authors, dates, URLs, and all raw source fields required for provenance.
- `deduplicate(records: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]` applies DOI, base arXiv, authoritative identity, normalized title, then recorded fuzzy evidence; it never joins records solely because a repository URL matches.

- [ ] **Step 1: Write failing unit tests for mapping-shaped catalogue extraction, DOI normalization, arXiv-version normalization, title normalization, exact duplicate merges, threshold fuzzy candidates, and 461-record assertion.**

```python
def test_extracts_mapping_catalogue_and_preserves_key() -> None:
    records = phase1.extract_records({"papers": {"2401.00001v2": {"title": "A"}}})
    assert records == [("2401.00001v2", {"title": "A"})]
```

- [ ] **Step 2: Run the targeted test module and confirm it fails before `phase1_map.py` exists.**

```bash
nix develop -c python -m unittest tests.test_survey_phase1 -v
```

- [ ] **Step 3: Implement schema-tolerant flattening.** Retain `catalog_key`, `arxiv_version_id`, `arxiv_id`, abstract, categories, dates, source URLs, cache hash, and query provenance; do not serialize Python dict representations into evidence columns.
- [ ] **Step 4: Implement ordered deduplication and a full lineage table.** Store `dedup_rule`, confidence, candidate similarity, retained/preferred manifestation rationale, source group IDs, and every record-to-work mapping.
- [ ] **Step 5: Implement automatic lanes and priority score exactly from the frozen vocabulary.** Preserve individual matched terms in JSON columns so a later reviewer can explain any assignment.
- [ ] **Step 6: Write all Phase-1 products and Parquet with explicit schema.** Make the command fail when `--expected-records 461` is not met; never overwrite a prior output with a changed catalogue hash.
- [ ] **Step 7: Run Phase 1 against the pinned catalogue.** Capture command, stdout/stderr, input hashes, output hashes, and counts in `survey/build/phase1_run.json`.

```bash
nix develop -c survey-phase1 \
  --catalog LLM-inference-on-FPGA-papers/data/catalog.json \
  --config survey/config/scope.yaml --out survey/build --expected-records 461
```

- [ ] **Step 8: Re-run in a clean output directory and byte-compare all deterministic CSV/Parquet/JSON outputs.**
- [ ] **Step 9: Commit mapping code, tests, and generated evidence.**

```bash
git add survey tests/test_survey_phase1.py
git commit -m "survey: map and deduplicate pinned corpus"
```

## Task 3: Complete controlled Phase-1 screening and project-family consolidation

**Files:**
- Create: `survey/scripts/finalize_screening.py`
- Create: `survey/data/screening_decisions.csv`
- Create: `survey/build/phase1_exclusions.csv`
- Create: `survey/build/project_families.csv`
- Create: `survey/build/screening_audit.md`
- Create: `tests/test_survey_screening.py`

**Interfaces:**
- `validate_decisions(mapping: DataFrame, decisions: DataFrame) -> DataFrame` requires exactly one final A/B/C/D/X disposition for every source record and exactly one controlled reason for each X record.
- `make_project_families(screened: DataFrame) -> DataFrame` assigns one stable family ID per related implementation, retaining every linked `work_id` and evidence source.
- `screening_decisions.csv` contains a reviewer decision and evidence location for every final disposition; automatic classification remains source metadata, never the sole final decision.

- [ ] **Step 1: Write failing tests that reject blank final levels, included X records, excluded non-X records, uncontrolled exclusion codes, and families without a primary work.**
- [ ] **Step 2: Run the tests and verify they fail before the validator exists.**
- [ ] **Step 3: Seed screening decisions from the Phase-1 queue, then adjudicate records in the protocol order.** Screen provisional A and C first; screen missing/conflicting records next; then B, D, and non-zero X. For each record, inspect title/abstract and the local PDF when it controls a route or ambiguous exclusion.
- [ ] **Step 4: Apply one controlled decision per record.** Use `X_LLM_FOR_EDA` for LLM-to-HDL/P&R papers, `X_NOT_FPGA` for unrelated hardware work, and `X_SECONDARY` for surveys; preserve transferable transformer/ViT, compiler, and component papers at B/C/D when their evidence satisfies the supplied criteria.
- [ ] **Step 5: Consolidate manifestations and assign project-family IDs.** Record every preprint/conference/revision link and select the preferred manifestation using the stated ordering.
- [ ] **Step 6: Generate the exclusion, family, and screening-audit reports.** The audit must list final counts, all decision evidence paths, duplicate/version decisions, reviewer sample/re-review design, and unresolved but non-blocking uncertainty.
- [ ] **Step 7: Run screening validation and require 461 decisions.**

```bash
nix develop -c python survey/scripts/finalize_screening.py \
  --mapping survey/build/phase1_mapping.csv \
  --decisions survey/data/screening_decisions.csv --out survey/build
nix develop -c python -m unittest tests.test_survey_screening -v
```

- [ ] **Step 8: Commit controlled classifications and the family map.**

```bash
git add survey tests/test_survey_screening.py
git commit -m "survey: finalize Phase-1 classifications"
```

## Task 4: Select the 25–40 family deep-review set and extract RQ1–RQ6 evidence

**Files:**
- Create: `survey/templates/deep_review.csv`
- Create: `survey/scripts/select_deep_review.py`
- Create: `survey/data/deep_review_manual.csv`
- Create: `survey/build/deep_review.csv`
- Create: `survey/build/deep_review.md`
- Create: `tests/test_survey_selection.py`

**Interfaces:**
- `score_family(family: Series) -> int` returns 0–10 using causal-LM relevance, distinct route, artifact availability, open-toolchain migration, and quantitative evidence.
- `select_families(families: DataFrame, reviews: DataFrame) -> DataFrame` includes mandatory families, all eligible score≥7 families up to 40, and enforces the 30% family cap unless all Level A work requires the exception.
- `deep_review.csv` has all protocol RQ1–RQ6 fields, contains exactly one row per selected project family, and cites every non-empty decision-critical claim.

- [ ] **Step 1: Write failing tests for mandatory A/C/artifact control inclusion, stable lexical tie-breaks, score calculation, 25–40 range, and route-family 30% cap.**
- [ ] **Step 2: Run selection tests to prove the selector does not exist.**
- [ ] **Step 3: Add the complete RQ1–RQ6 header and strict column validation.** No invented field aliases; preserve blank unknowns and describe them as `not reported` in Markdown rather than guessing.
- [ ] **Step 4: Score families from the final screening evidence.** Include the compiler-lab artifact-control row, every Level A with accessible evidence, each distinct executable C route, open block-level artifacts, and one incompatibility case per material route family.
- [ ] **Step 5: Fill the selected family rows from PDFs, repository files, and API evidence.** Pin paper pages/sections and repository commit/path in `evidence_locations`; distinguish observed, documented, and inferred values in `notes`.
- [ ] **Step 6: Render the human-readable table.** Link each family row to its complete CSV record and make unknown licensing/tooling explicit.
- [ ] **Step 7: Run selection and schema tests, then review coverage against target composition.**

```bash
nix develop -c python survey/scripts/select_deep_review.py \
  --families survey/build/project_families.csv \
  --reviews survey/data/deep_review_manual.csv --out survey/build
nix develop -c python -m unittest tests.test_survey_selection -v
```

- [ ] **Step 8: Commit the frozen deep-review sample and extraction evidence.**

```bash
git add survey tests/test_survey_selection.py
git commit -m "survey: extract deep-review route evidence"
```

## Task 5: Audit repositories, licences, and identifier metadata

**Files:**
- Create: `survey/scripts/enrich_metadata.py`
- Create: `survey/scripts/audit_repositories.py`
- Create: `survey/build/api_retrieval_log.csv`
- Create: `survey/build/artifact_inventory.csv`
- Create: `survey/build/repository_audit.csv`
- Create: `survey/build/api-cache/index.json`
- Create: `tests/test_survey_artifacts.py`

**Interfaces:**
- `cached_request(service: str, identifier: str, url: str) -> CacheEntry` stores raw response path, HTTP status, retrieval timestamp, request URL, response SHA-256, and error body hash.
- `audit_repository(url: str, commit: str | None) -> dict[str, object]` records default branch, commit, archive state, release tags, licence evidence, source closure, build files, CI, vendor tools/IP, FPGA families, and tests.
- An inaccessible, rate-limited, unlicensed, or malformed artifact remains a negative evidence row with an appropriate field/failure code; it is not dropped.

- [ ] **Step 1: Write failing offline tests for cache-index integrity, GitHub URL normalization, licence-state distinction (`detected`, `none_detected`, `unavailable`), and mandatory artifact fields.**
- [ ] **Step 2: Run artifact tests and confirm the required script contracts are absent.**
- [ ] **Step 3: Implement cache-first API retrieval.** Use documented GitHub, Crossref, OpenAlex, Unpaywall, and arXiv endpoints only when a stable identifier is present; record retrieval dates and no secrets in output.
- [ ] **Step 4: Implement source-closure auditing.** Pin repository commits; enumerate submodules, generated/omitted RTL, tool declarations, vendor headers, binaries, encrypted IP, supported hardware, test fixtures, and licence evidence.
- [ ] **Step 5: Audit every selected deep-review artifact and all eight route hypotheses.** Clone only repositories selected for executable compatibility work; otherwise use API/tree evidence with a recorded limitation.
- [ ] **Step 6: Run offline integrity tests and inspect the audit for empty claimed repositories, duplicate URLs, and silently missing licence states.**
- [ ] **Step 7: Commit audit code, indexes, inventories, and redacted response metadata.**

```bash
git add survey tests/test_survey_artifacts.py
git commit -m "survey: audit reusable artifacts and licences"
```

## Task 6: Execute the common compatibility triage for five to eight routes

**Files:**
- Create: `survey/scripts/run_compatibility.py`
- Create: `survey/compatibility/R1-mlir-circt/`
- Create: `survey/compatibility/R2-parameterized-rtl/`
- Create: `survey/compatibility/R3-mase/`
- Create: `survey/compatibility/R4-mlir-hls/`
- Create: `survey/compatibility/R5-finn/`
- Create: `survey/compatibility/R6-hls4ml/`
- Create: `survey/compatibility/R7-open-accelerator/`
- Create: `survey/compatibility/R8-cpu-fpga-fallback/`
- Create: `survey/build/compatibility_summary.csv`
- Create: `tests/test_survey_compatibility.py`

**Interfaces:**
- `RouteReceipt` fields: `route_id`, source/artifact commits and hashes, environment manifest, executed commands, expected/actual stage, status, frozen tolerance, `failure_code`, generated RTL paths, lint/simulation/synthesis evidence, and next bounded action.
- `run_route(route: RouteSpec, budget_hours: int) -> RouteReceipt` stops triage at 16 hours if complete elaboratable RTL is absent and no bounded corrective action exists; viable routes may extend to 40 hours.
- Each route directory contains `README.md`, `manifest.json`, `commands.sh`, `stdout.log`, `stderr.log`, and all generated report references or an explicit unattainable-stage result.

- [ ] **Step 1: Write failing tests for all eight route IDs, allowed failure codes, immutable command hashes, route receipt schema, and rule that a failed hard gate cannot have `decision=PRIMARY`.**
- [ ] **Step 2: Run the tests and confirm no compatibility framework exists.**
- [ ] **Step 3: Define M0, M1, M2, and M3 fixtures with frozen static shapes and numerical acceptance fields.** M2 must specify two blocks, 128-wide model, four heads, 256 FFN, vocabulary 256, max sequence 32, and four-token greedy decode; do not call an unimplemented M2 result passed.
- [ ] **Step 4: Run the existing compiler-lab R1 path first.** Execute environment check, TinyStories capture/lowering, smoke tests, `pytest`, Verilator lint, and generic Yosys synthesis. Preserve the current repository's documented failure state as a result rather than repairing unrelated code.
- [ ] **Step 5: Triage R2 through R8 against their pinned artifact audits.** Attempt a reproducible minimal build, source closure, M0 import/lowering, and independent lint/elaboration when source is accessible; record `F_SOURCE_MISSING`, `F_LICENSE`, `F_VENDOR_IP`, or other protocol code at the first gating failure.
- [ ] **Step 6: For each viable route, perform M0 operator coverage, M1 block generation, deterministic simulation comparison, and generic Yosys synthesis.** Store test vectors, reference outputs, tolerance declaration, raw logs, and resource statistics.
- [ ] **Step 7: Execute M2 stateful decode only for a route with all preceding gates.** Verify persistent KV state and token-identical greedy decode against the frozen reference; report failure if the loop remains host-controlled.
- [ ] **Step 8: Validate all route receipts and commit the compatibility evidence.**

```bash
nix develop -c python survey/scripts/run_compatibility.py --route R1 --out survey/compatibility/R1-mlir-circt
nix develop -c python -m unittest tests.test_survey_compatibility -v
git add survey tests/test_survey_compatibility.py
git commit -m "survey: record route compatibility triage"
```

## Task 7: Complete the MLIR/CIRCT sub-survey and route decision matrix

**Files:**
- Create: `survey/scripts/mlir_stage_matrix.py`
- Create: `survey/build/mlir_circt_stage_matrix.csv`
- Create: `survey/build/mlir_circt_stage_matrix.md`
- Create: `survey/build/decision_matrix_scored.csv`
- Create: `survey/build/route_selection.md`
- Create: `survey/templates/decision_matrix.csv`
- Create: `tests/test_survey_decision.py`

**Interfaces:**
- `stage_status(project: str, stage: str) -> Literal["native", "extension_available", "manual_implementation", "missing"]` requires an evidence location for every non-missing value.
- `score_route(row: Mapping[str, object]) -> float` calculates the exact 0–100 weighted total with weights 25/20/15/15/10/10/5.
- `choose_routes(routes: DataFrame) -> tuple[str, str]` returns a primary that passes all hard gates and a fallback in a different route family; it raises if no primary passes.

- [ ] **Step 1: Write failing tests for all 20 stage-matrix transformations, evidence-required statuses, score arithmetic, hard-gate override, and distinct primary/fallback route family.**
- [ ] **Step 2: Run decision tests and verify the absent implementation fails.**
- [ ] **Step 3: Extract MLIR/CIRCT evidence from pinned source, local compiler-lab tests, deep-review papers, and artifact audits.** Mark a stage native only if the pinned source exercises it in a test/example; a declared dialect alone must remain non-native.
- [ ] **Step 4: Answer H1, H2, and H3 with bounded evidence.** Tie each claim to R1 compatibility logs or a documented artifact result; do not treat generic MLIR terminology as transformer support.
- [ ] **Step 5: Fill all eight decision-matrix rows.** Enter `false` hard-gate values at each observed block, scores only when evidence exists, and a direct evidence link for every non-zero score.
- [ ] **Step 6: Compute scores and select a primary route only if every hard gate passes.** If no primary passes, record `NO_PRIMARY_ROUTE_PASSED` and choose no misleading primary; name the best next evidence-gathering route and a distinct fallback candidate.
- [ ] **Step 7: Run tests and commit the stage matrix and route decision.**

```bash
nix develop -c python survey/scripts/mlir_stage_matrix.py --out survey/build
nix develop -c python -m unittest tests.test_survey_decision -v
git add survey tests/test_survey_decision.py
git commit -m "survey: score routes and document MLIR gaps"
```

## Task 8: Render D13–D16 and verify the complete evidence package

**Files:**
- Create: `survey/scripts/make_figures.py`
- Create: `survey/scripts/build_report.py`
- Create: `survey/build/corpus_flow.mmd`
- Create: `survey/build/route_family_comparison.md`
- Create: `survey/build/route_family_comparison.csv`
- Create: `survey/build/timeline.mmd`
- Create: `survey/build/final_report.md`
- Create: `survey/build/final_report.tex`
- Create: `survey/build/final_report.pdf`
- Create: `tests/test_survey_report.py`

**Interfaces:**
- `validate_deliverables(root: Path) -> list[str]` checks D1–D16, each evidence link/path, declared count consistency, report input hashes, selection bounds, hard-gate assertions, and PDF existence.
- `render_corpus_flow(flow: dict[str, int]) -> str` uses final—not auto—levels and includes the 461 source record count.
- `build_report(...) -> Path` refuses to render a completion report if required evidence files, command receipts, or decision-matrix hard-gate fields are missing.

- [ ] **Step 1: Write failing report tests for all D1–D16 paths, 461 count consistency, deep-review bounds, valid Mermaid syntax, reported hard-gate status, cited selected-family evidence, and non-empty PDF.**
- [ ] **Step 2: Run the report test before implementing the renderer and confirm it fails.**
- [ ] **Step 3: Implement deterministic figures and comparison tables.** Use final Phase-1 counts, current date-independent protocol timeline, route taxonomy, and the 20-row stage matrix; do not substitute screenshots for data.
- [ ] **Step 4: Render a self-contained final report.** Cover question, scope/amendment, methods, corpus flow, final A–D/X results, 25–40 family review, repository/licence evidence, compatibility results, MLIR/CIRCT hypotheses, decision matrix, primary/fallback status, limitations, and reproduction commands.
- [ ] **Step 5: Generate LaTeX and PDF with `pdflatex` twice.** Fail on unresolved references or absent sources; retain the command transcript and PDF SHA-256.
- [ ] **Step 6: Run the full survey test set from a clean environment.**

```bash
nix develop -c python -m unittest discover -s tests -p 'test_survey_*.py' -v
nix develop -c python survey/scripts/build_report.py --root . --out survey/build
pdflatex -interaction=nonstopmode -output-directory survey/build survey/build/final_report.tex
pdflatex -interaction=nonstopmode -output-directory survey/build survey/build/final_report.tex
```

- [ ] **Step 7: Re-run Phase 1, selection, audits, compatibility receipts, and report rendering from a clean survey output directory.** Compare hashes for deterministic inputs/outputs and describe any time-stamped expected differences.
- [ ] **Step 8: Commit the final evidence package.**

```bash
git add survey tests/test_survey_report.py
git commit -m "survey: publish reproducible route assessment"
```

## Completion audit

- [ ] D1 is a frozen, source-hashed protocol with the explicit 461-record amendment.
- [ ] D2 records all three repository commits/remotes, input hashes, tool versions, API retrieval index, and full command logs.
- [ ] D3–D6 prove every source record was normalized, lineage-preserved, classified once, and included/excluded with controlled evidence.
- [ ] D7–D9 prove project-family grouping, 25–40 deep-review extraction, and repository/artifact audit coverage.
- [ ] D10 contains one valid compatibility receipt for every tested route, including failures.
- [ ] D11 contains all 20 MLIR/CIRCT transformations and H1–H3 outcomes anchored to evidence.
- [ ] D12 scores each candidate route, applies hard-gate overrides, and identifies a primary only when eligible plus a different-family fallback.
- [ ] D13–D15 contain reproducible Mermaid source and final counts/timeline.
- [ ] D16 cites evidence per substantive claim, renders to a non-empty PDF, and lists known limitations (including any absent primary route).
- [ ] The clean rerun and offline tests verify that no output depends on unrecorded local state.
