# Route-compatibility survey (LLM-inference-on-FPGA papers)

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
