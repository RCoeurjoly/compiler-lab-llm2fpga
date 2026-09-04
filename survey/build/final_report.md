# Executable LLM2FPGA survey evidence report

## Question, scope, and amendment

This report asks which implementation route has the strongest evidence-supported
prospect of reproducible, end-to-end causal-language-model inference on an FPGA
with a substantially open toolchain. The frozen protocol amendment reconciles
the supplied catalogue count **459 to 461**: the commit-pinned source contains
**461 source records**, and the study question and eligibility rules are
unchanged. Evidence: `survey/protocol.md#lines=5-17`; `survey/config/scope.yaml`;
`LLM-inference-on-FPGA-papers/data/catalog.json`; `survey/build/provenance.json`.

## Methods and corpus lineage

The package preserves each source record in
`survey/build/records_normalized.csv`, records duplicate/version lineage in
`survey/build/duplicate_groups.csv`, performs rule-based triage in the immutable
`survey/build/phase1_mapping.csv`, and retains adjudicated screening decisions in
`survey/data/screening_decisions.csv`. Source and command provenance are pinned
in `survey/build/provenance.json`, `survey/build/api_retrieval_log.csv`, and
`survey/build/phase1_run.json`.

The final (not automatic) corpus flow is **461 source records**, **456 unique works**, and **5 duplicate manifestations**. Final decisions are
**A=30, B=57, C=75, D=68, X=231**: **230 included records** and 231 controlled
exclusions. The final reconciliation and the immutable Phase 1 hashes are in
`survey/build/final_flow_counts.json`; the readable audit is
`survey/build/screening_audit.md`.

## Families, sample, and artifact audit

The controlled grouping has **226 project families** represented by 230
included work rows in `survey/build/project_families.csv`. The bounded manual
sample has **36 reviewed project-family/control rows**, satisfying the planned
25--40 range, with RQ1--RQ6 evidence recorded in
`survey/build/deep_review.csv` and `survey/build/deep_review.md`.

Artifact and licence claims remain evidence-qualified: the complete reviewed
set is represented in `survey/build/artifact_inventory.csv`, while the nine
repository observations (including source-closure and licence limitations) are
in `survey/build/repository_audit.csv`. The API evidence index is
`survey/build/api-cache/index.json`; raw API bodies are not required to render
or validate this offline package.

## Compatibility and MLIR/CIRCT evidence

Every tested route R1--R8 has a receipt, command script, standard output, and
standard error under the checked-in compatibility receipt directories; the checked summary is
`survey/build/compatibility_summary.csv`. In particular,
`survey/compatibility/R1-mlir-circt/manifest.json` records the final observed
R1 stop at `RTL_GENERATION/F_SOURCE_MISSING`; its reproducible command and
observations are `survey/compatibility/R1-mlir-circt/commands.sh`,
`survey/compatibility/R1-mlir-circt/stdout.log`, and
`survey/compatibility/R1-mlir-circt/stderr.log`. This is not an RTL pass.

The source-faithful MLIR/CIRCT catalog is **3 projects x 20 canonical transformations = 60 assessed cells**, rather than a claim that there are only
20 assessments. It retains source evidence and H1--H3 bounded conclusions in
`survey/build/mlir_circt_stage_matrix.csv` and
`survey/build/mlir_circt_stage_matrix.md`, including the canonical
weight-loading interface transformation.

The bounded hypothesis outcomes are explicit: **H1 — unsupported for the current route.** **H2 — bounded/partial support only.** **H3 — inconclusive.** Their source-faithful evidence and limits are recorded in
`survey/build/mlir_circt_stage_matrix.md#lines=90-94`.

## Selection result

`survey/build/decision_matrix_scored.csv` evaluates the frozen hard gates
before any weighted score. The selection outcome is
**NO_PRIMARY_ROUTE_PASSED**. **Primary route: none.** All R1--R8 candidates are
ineligible, so no score is used to promote a primary route.

**R1 is the ineligible next evidence-gathering route**: its required next step
is to restore the pinned native-SV helper, regenerate RTL, and then obtain
independent lint and synthesis evidence. **R2 is an ineligible different-family hypothesis**: its proprietary RTL and `SOURCE_CLOSURE/F_VENDOR_IP` finding make
it neither a selected fallback nor a primary. These statements are reproduced
from `survey/build/route_selection.md` and their receipt evidence, including
`survey/compatibility/R1-mlir-circt/manifest.json`.

## Reproduction and limits

Run the offline validation and renderer from the repository root:

```sh
nix develop -c python -m unittest discover -s tests -p 'test_survey_*.py' -v
nix develop -c python survey/scripts/build_report.py --root . --out survey/build
```

The renderer writes date-independent Mermaid source for the final corpus flow,
route-family comparison, and canonical protocol sequence; it invokes `pdflatex`
twice and records its transcript plus PDF SHA-256 in
`survey/build/final_report_build.json`. The pinned `flake.nix` and `flake.lock`
development shell supplies the **declared pdflatex** command, so rendering does
not depend on a host-profile TeX installation. The evidence supports no eligible
primary route, makes no completed end-to-end causal-LM claim, and retains the
protocol limitation that the target **board remains unspecified**. A future
route must obtain new, attributable source, licence, hard-gate, and independent
execution evidence before this conclusion can change.
