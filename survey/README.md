# Executable LLM-to-FPGA survey

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
