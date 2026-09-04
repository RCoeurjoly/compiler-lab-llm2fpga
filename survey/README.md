# LLM-to-FPGA survey

## Route-compatibility scanner

This scanner is separate from the executable evidence pipeline described below.

This directory contains a corpus-level route survey over the 461 papers in
`LLM-inference-on-FPGA-papers/data/catalog.json`.

Goal:

- Classify each catalog paper against candidate FPGA implementation routes
  relevant to LLM2FPGA migration:
  - `MLIR/CIRCT`
  - `HLS`
  - `overlay`
  - `parameterized RTL`
  - `dataflow`
  - `CPU+FPGA fallback`
- Mark whether each paper appears **realistically reusable** for LLM2FPGA at this
  triage level.

Generation command:

```sh
python3 survey/route_compatibility_survey.py \
  --catalog LLM-inference-on-FPGA-papers/data/catalog.json \
  --csv survey/route-compatibility-survey.csv \
  --summary survey/route-compatibility-survey.md \
  --reusable-out survey/route-compatibility-reusable-candidates.csv
```

Notes:

- `route-compatibility-survey.csv` has one row per catalog record and route
  evidence columns per family.
- `realistically_reusable` has values `high|medium|low|none`.
  - **high/medium** are candidates for the LLM2FPGA short-list.
  - The scan now uses full-paper text from cached PDFs via `pdftotext`, with a
    fallback to title/abstract/category metadata only when a PDF is missing or unreadable.
- `route-compatibility-reusable-candidates.csv` is the short list (now generated from full-paper matches) with
  `high` or `medium` reusability labels.
- `route-compatibility-survey.md` is a generated summary.

## Reuse discovery from the survey output

Use the same script with query flags for reusable-paper retrieval:

For fast iteration, reuse a previously generated survey CSV directly (no PDF re-scan):

```sh
python3 survey/route_compatibility_survey.py \
  --precomputed-csv survey/route-compatibility-survey.csv \
  --query-keywords "yosys nextpnr kintex pytorch" \
  --search-out survey/reuse-keyword-hitlist-fast.csv
```

This works best when you already have `route-compatibility-survey.csv` from a prior full run.

Keyword search:

```sh
python3 survey/route_compatibility_survey.py \
  --query-keywords "yosys nextpnr kintex pytorch mlir circt" \
  --keyword-match-mode any \
  --search-out survey/reuse-keyword-hitlist.csv
```

Semantic query (fallbacks to local TF-IDF if sentence-transformers is unavailable):

```sh
python3 survey/route_compatibility_survey.py \
  --query-semantic "FPGA flow with MLIR and CIRCT targeting nextpnr and Yosys" \
  --semantic-top-k 50 \
  --search-out survey/reuse-semantic-hitlist.csv
```

Both modes default to filtering `high` and `medium` reusable labels. Adjust with:

```sh
--search-reusable-filter all
--search-no-reusable-filter
--query-keywords "...\" --query-semantic "..."
```

If you want pure keyword behavior for semantic text (offline-safe), add:

```sh
--fallback-keyword-only
```
## Executable evidence pipeline

This directory contains the survey-only evidence pipeline. It does not change
the compiler implementation. The frozen source population is all 461 records
in `LLM-inference-on-FPGA-papers/data/catalog.json` at commit
`95fd9b9a509f275dd3cfdb3360b33dbcca7429f0`.

The supplied protocol described 459 records. The pinned catalogue contains
461, so `protocol.md` records an explicit 459 → 461 snapshot amendment. No
record is removed to preserve the stale prose count, and every later corpus
flow must begin with 461 source records.

## Reproduce Task 1

Initialize the pinned inputs, enter the Nix environment, run the focused tests,
and regenerate the evidence:

```bash
git submodule update --init LLM-inference-on-FPGA-papers
nix develop -c python -m unittest tests.test_survey_scope -v
nix develop -c python survey/scripts/common.py \
  --root . \
  --provenance survey/build/provenance.json \
  --environment survey/build/environment_manifest.json
```

The dedicated interpreter is also exposed as `.#surveyPython` and through
`nix develop .#survey`.

`survey/build/` is an evidence directory, not disposable build output. Evidence
needed by D2–D16 is committed. Only raw, reproducible responses below
`survey/build/api-cache/` are ignored; retrieval logs, hashes, and derived
tables remain tracked. Never place tokens, authorization headers, email
credentials, or credential-bearing remote URLs in survey outputs.

## Frozen inputs and decisions

- `protocol.md` is the human-readable frozen protocol.
- `config/scope.yaml` is its machine-readable contract.
- `data/manual_overrides.csv` records immutable record lineage and reviewer
  decisions; rows are added, never substituted for catalogue records.
- `data/route_vocabulary.csv` supplies the route-family controlled vocabulary.
- `scripts/common.py` validates scope and emits atomic, UTF-8 JSON evidence.

All later automation must retain one lineage row per source `record_id`, even
when manifestations are grouped under a shared `work_id` or
`project_family_id`.
