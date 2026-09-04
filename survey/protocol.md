# Executable Survey Protocol for Open LLM-to-FPGA Implementation Routes

Status: frozen for the commit-pinned source snapshot described below.

## Catalogue amendment: 459 → 461

The supplied protocol was written against a catalogue described as containing
459 records. The checked-out `LLM-inference-on-FPGA-papers` gitlink is commit
`95fd9b9a509f275dd3cfdb3360b33dbcca7429f0`; its
`data/catalog.json` contains 461 keyed paper records. This frozen study therefore
uses **461 source records**.

This amendment corrects only the snapshot count. It does not change the study
question, eligibility criteria, level definitions, review treatment,
deduplication rules, route hypotheses, or evidence thresholds. No record may be
dropped to recreate 459. All 461 retain immutable source lineage, including
duplicates, retractions, and exclusions. Later counts must reconcile to 461.

## Study design and question

The work is a systematic mapping study followed by a focused artifact-based
technical review. The unit of screening is a bibliographic record. The unit of
deep review is a work or project family. Conference papers, journal extensions,
preprints, reports, and repositories for the same implementation normally share
a `work_id` or `project_family_id` without losing their individual `record_id`s.

> Which implementation route has the highest evidence-supported probability of
> producing reproducible, end-to-end causal-language-model inference on an FPGA
> using a substantially open toolchain, and what reusable components,
> incompatibilities, and fallback routes follow from the literature and
> artifact evidence?

The survey is not restricted to MLIR. MLIR/CIRCT is a focused sub-survey and the
current implementation hypothesis, while parameterized RTL, HLS, dataflow,
overlay, and CPU/FPGA fallback routes remain eligible.

## Levels

Each work receives one primary level and may receive multiple topic tags. Level
is survey relevance, not a quality ranking.

| Level | Operational definition | Required evidence | Review treatment |
|---|---|---|---|
| A | End-to-end or nearly end-to-end autoregressive language-model inference on FPGA | At least one complete decoder stack or model; token-generation loop, prefill, or decode described; FPGA is a material execution platform | Full RQ1–RQ6 extraction; artifact inspection when available |
| B | Transformer or language-model accelerator implementing a complete block or a substantial fraction of the operator stack | Attention, feed-forward network, normalization, scheduling, memory architecture, or equivalent block-level coverage | Full extraction when architecture is transferable |
| C | Compiler, framework, generator, HLS, MLIR, overlay, or graph-lowering route capable of producing FPGA hardware | Credible model, graph, program, or kernel → RTL/HLS/netlist/bitstream path | Full extraction for distinct executable routes |
| D | Enabling component or adjacent method with direct transfer potential | MatMul, attention, softmax, normalization, RoPE, quantization, KV cache, memory scheduling, verification, or an adjacent accelerator technique | Mapping only unless selected to resolve a route-specific gap |
| X | Outside the study scope | Does not satisfy A–D after full title/abstract inspection | Exclude with one controlled reason code |

## Eligibility

A record is included when all general criteria and at least one technical
criterion are satisfied.

General criteria:

- English title and abstract, or a full English paper.
- Sufficient bibliographic identity to establish a distinct work.
- Publicly inspectable abstract, paper, preprint, or technical report.
- Material relevance to FPGA inference, FPGA hardware generation, or a
  component necessary for transformer inference.
- Research paper, project report, dissertation chapter, or primary artifact
  documentation. Secondary surveys may guide searching but do not supply
  implementation evidence rows.

Technical criteria (one or more):

- FPGA implementation of an LLM, causal LM, transformer, BERT-like model,
  decoder, encoder, or attention system.
- Hardware generation from PyTorch, ONNX, TensorFlow, MLIR, an internal graph
  IR, C/C++, a DSL, or a parameterized architecture.
- FPGA implementation of attention, MatMul/GEMM, feed-forward layers, softmax,
  LayerNorm, RMSNorm, RoPE, quantization, sparsity, KV-cache management, or
  token-generation control.
- An overlay, dataflow engine, systolic array, vector engine, or programmable
  accelerator shown to support transformer-relevant workloads.
- Verification or synthesis infrastructure directly applicable to a proposed
  open-source route.

Training and vision-transformer papers are not excluded automatically. They
remain B, C, or D when their architecture, transformations, quantization,
attention, or memory organization transfers directly.

### Controlled exclusions

| Code | Rule |
|---|---|
| `X_NOT_FPGA` | No FPGA, reconfigurable-hardware, RTL-generation, or directly transferable hardware-compilation contribution |
| `X_LLM_FOR_EDA` | Uses an LLM for HDL, RTL, place-and-route, or EDA automation but does not implement LLM inference on FPGA |
| `X_TRAINING_ONLY` | Training-only architecture without a transferable inference contribution |
| `X_NON_LM_MODEL` | Unrelated workload without a transformer-relevant compiler or operator contribution |
| `X_VIT_NO_TRANSFER` | Vision-transformer work without reusable attention, dataflow, compiler, quantization, or memory techniques |
| `X_ASIC_GPU_ONLY` | Non-FPGA work without a reusable compiler IR, generator, scheduling method, or FPGA-relevant architecture |
| `X_PERFORMANCE_MODEL_ONLY` | Analytical model or simulation without an implementable architecture or compiler route |
| `X_SECONDARY` | Survey, editorial, slide deck, or non-primary summary retained only for searching |
| `X_NO_EVIDENCE` | Metadata is insufficient and no full text or authoritative abstract can be recovered |
| `X_DUPLICATE` | Duplicate bibliographic manifestation merged into another work |
| `X_RETRACTED` | Retracted or withdrawn work retained only in provenance records |

## Automated triage and human screening

`scope.yaml` freezes the regular expressions for FPGA, language-model,
compiler, component, end-to-end, and negative concepts. Automation assigns
queues, never final decisions:

```text
direct lane    = FPGA AND LM
compiler lane  = compiler AND (FPGA OR RTL/hardware)
component lane = FPGA AND component

A_candidate = direct lane AND end-to-end
B_candidate = direct lane AND NOT end-to-end
C_candidate = compiler lane
D_candidate = component lane AND NOT direct lane
X_candidate = no positive lane
```

Manual review is mandatory for absent or short abstracts, conflicting positive
and negative matches, tied levels, generic-only matches, non-FPGA compiler
works, identifier disagreements, and vision, encoder-only, or training systems.
The frozen score prioritizes queues; it never accepts a record automatically.

Screen provisional A then C, ambiguous records, B, D, and finally X records
with positive scores. Two reviewers independently screen all A and C records
and a random 20% of B, D, and X. Disagreements use full-text adjudication. A
single researcher instead repeats a blind sample after at least one week and
reports intra-review agreement.

## Deduplication and lineage

Apply these rules in order while retaining every source record:

1. Exact normalized DOI.
2. Exact base arXiv identifier after removing a version suffix.
3. Exact authoritative identifier such as OpenAlex, Semantic Scholar, or
   PubMed.
4. Exact normalized title after Unicode NFKC, lowercasing, line-break
   dehyphenation, punctuation removal, and whitespace collapse.
5. Title similarity ≥95/100 with the same first author and publication years
   differing by at most one.
6. Title similarity ≥92/100 with at least two matching authors and a matching
   DOI prefix, arXiv identifier, or distinctive subtitle.
7. Manual adjudication of every remaining fuzzy candidate.

Preprint, workshop, conference, and journal manifestations share one `work_id`
but retain distinct `record_id`s. Prefer a corrected peer-reviewed version with
artifact, then peer-reviewed version, latest non-withdrawn preprint, then
repository manuscript. Repository sharing alone never proves two papers are one
work. Clear releases or extensions of the same system may share a
`project_family_id` for deep review.

## Deep review and extraction

Select approximately 25–40 project families deterministically. Mandatory
inclusions are all supported Level A families; each distinct executable Level C
route; projects already attempted in either LLM2FPGA repository; blocker
components; public end-to-end or block-level artifacts; and an informative
negative case for each route family. Then maximize diversity among B and D.
Score direct decoder relevance 0–3; distinct route 0–2; public artifact 0–2;
open-toolchain migration 0–2; and evidence quality 0–1. Include scores ≥7 under
the 40-family ceiling, with stable tie-breaking by artifact availability,
route diversity, model coverage, recency, then `project_family_id`. No route
family exceeds 30% unless it contains every Level A implementation.

RQ extraction records:

- **RQ1 route:** input frontend, source and intermediate IRs, backend,
  architecture, control model, and generation mode.
- **RQ2 model coverage:** family, prefill, decode, token loop, attention, FFN,
  normalization, RoPE, KV cache, softmax, sampling, and completeness.
- **RQ3 reusable components:** frontend, passes, RTL, HLS, runtime, tests, and
  qualified reuse notes.
- **RQ4 openness:** source, HLS, synthesis, and place-and-route openness;
  required closed tools or IP; vendor primitives; and migration work.
- **RQ5 feasibility:** minimum model, precision, shape, memory, device, resource,
  clock, throughput, latency, and power evidence.
- **RQ6 verification:** reference model, vectors, simulators, formal support,
  environment, interfaces, and reproduction status.

Repository evidence is pinned by URL and commit and audits licenses, submodules,
generated files, dependencies, supported devices, tests, and required IP. A
public repository does not establish a usable code, hardware, model, or IP
license.

## Candidate routes and controlled vocabulary

The initial hypotheses are MLIR/CIRCT; a parameterized RTL decoder generator;
HLS or explicit scheduling; quantized dataflow; programmable overlays; and a
software-controlled CPU/FPGA fallback. Phase-1 evidence may add, merge, or
eliminate hypotheses. `route_vocabulary.csv` freezes their machine-readable
names.

### Hard eligibility gates

A primary route requires all of the following:

- Source and required artifacts are accessible.
- Applicable licenses permit evaluation and intended reuse.
- A minimal configuration builds reproducibly.
- A plausible path reaches complete prefill or decode, not only isolated
  MatMul.
- No indispensable proprietary IP remains in the final qualifying flow.
- Generated RTL is complete enough to lint and simulate independently.
- Compatibility testing fits the predefined budget.
- Numerical behavior is comparable against a deterministic software reference.

A proprietary tool may provide a reference baseline. A route requiring it
remains non-FOSS unless a tested replacement exists. Gate failure overrides the
decision score, and the fallback must be architecturally different from the
primary route.

### Decision matrix

Scores are 0–5 and weighted as `sum(score / 5 * weight)`:

| Criterion | Weight |
|---|---:|
| Probability of functioning demonstrator | 25 |
| FOSS-toolchain compatibility | 20 |
| End-to-end model coverage | 15 |
| Reusability and parameterization | 15 |
| Verification and auditability | 10 |
| Available-hardware feasibility | 10 |
| Performance potential | 5 |

Weighted total alone never selects a route.

## Common compatibility fixtures

Initial tests use batch size one and static shapes.

| Fixture | Configuration | Purpose |
|---|---|---|
| `M0-operators` | Int8/fixed-point MatMul; normalization; activation; RoPE; causal softmax; KV read/write | Determine exact operator and numerical support |
| `M1-block` | One decoder block, `d_model=64`, 4 heads, `d_ff=128`, sequence length 16 | Test scheduling, residuals, state, memory, and interfaces |
| `M2-tiny-lm` | Two decoder blocks, `d_model=128`, 4 heads, `d_ff=256`, vocabulary 256, maximum sequence 32, greedy decode of four tokens | Minimal end-to-end token-generation test |
| `M3-repository-fixture` | Existing TinyStories fixture from the compiler laboratory | Preserve continuity with the current PyTorch/MLIR smoke path |

Integer modules require identical outputs. Fixed-point approximations require a
frozen LSB tolerance; floating-point stages require frozen absolute and
relative tolerances; M2 requires token-identical greedy decode after
quantization is frozen. Tolerances may not change after observing results.

Each route escalates through environment reproduction, artifact completeness,
frontend import, operator coverage, RTL lint/elaboration, simulation
equivalence, generic synthesis, board implementation, stateful decode, and a
reproducibility rerun. Triage is capped at approximately 16 hours and promising
routes at 40. Suspend a route at 16 hours when complete elaboratable RTL is not
available and no bounded corrective action exists.

## Failure taxonomy

| Code | Meaning |
|---|---|
| `F_ENV` | Unpinned dependency, unavailable compiler version, or broken container |
| `F_SOURCE_MISSING` | Generated RTL references uncommitted modules |
| `F_LICENSE` | Required code, model, or IP has no usable license |
| `F_FRONTEND` | Unsupported operation, dynamic shape, custom operator, or graph mutation |
| `F_TYPE` | Quantized or fixed-point types cannot be represented or legalized |
| `F_LOWERING` | Operation remains in an unsupported dialect |
| `F_SCHEDULE` | Infeasible schedule, excessive unrolling, or uncontrolled resource duplication |
| `F_CONTROL` | Handshake deadlock or incorrect backpressure, reset, or token-loop semantics |
| `F_MEMORY` | Buffer mapping, banking, or port count is infeasible |
| `F_STATE` | KV cache or recurrent decode state is not preserved |
| `F_RTL` | Unsupported SystemVerilog, width/sign error, latch, or missing hierarchy |
| `F_VENDOR_IP` | Essential DSP, memory, AXI, HLS, or encrypted IP cannot be replaced |
| `F_SYNTH_RESOURCE` | Resource expansion makes the design infeasible |
| `F_TIMING` | Route fails the required clock |
| `F_NUMERIC` | Arithmetic exceeds the frozen tolerance |
| `F_INTERFACE` | Host, memory, streaming, or weight-loading interface is incomplete |

## MLIR/CIRCT sub-survey

The sub-survey asks which MLIR/CIRCT projects transform tensor or loop programs
into complete synthesizable hardware and which causal-LM transformations are
native, extensible, manual, or missing. A transformation counts as native only
when pinned source implements it and a test or documented example exercises it.
A dialect declaration is not support.

The stage matrix covers model capture, shape specialization, bufferization,
fixed-point legalization, MatMul tiling, QKV fusion, causal masking, softmax,
normalization, activations, RoPE, KV state, memory banking, scheduling,
backpressure, interfaces, memory inference, clock/reset, and device mapping.
It explicitly tests:

- **H1:** generic Torch-MLIR → Linalg → Handshake → HW/SV can produce an
  efficient complete decoder block without architecture-specific transforms.
- **H2:** Torch-MLIR is reusable as a frontend but the data path needs an
  architecture-specific generator or IR.
- **H3:** MLIR is most useful for orchestration and verification around
  parameterized compute and memory modules.

## Reproducibility and evidence policy

The compiler laboratory, papers repository, and sibling LLM2FPGA repository are
recorded by commit and remote. Catalogue and frozen input files are SHA-256
hashed. The Nix interpreter pins pandas, pyarrow, PyYAML, RapidFuzz, Unidecode,
requests, requests-cache, and tabulate. Generated JSON uses UTF-8, a trailing
newline, and atomic replacement.

Evidence needed by D2–D16 is tracked in git. Raw regenerable API responses under
`survey/build/api-cache/` are the sole cache exception; retrieval logs and
hashes remain evidence. Outputs must never contain credentials or authorization
headers. Final claims cite a paper location, pinned repository path, command
log, simulation or synthesis report, metadata response, or explicit reviewer
decision.

## Required deliverables

```text
D1  protocol.md
D2  provenance.json and API retrieval log
D3  records_normalized.csv
D4  duplicate_groups.csv and version-family decisions
D5  phase1_mapping.csv and phase1_mapping.parquet
D6  phase1_exclusions.csv
D7  project_families.csv
D8  deep_review.csv and deep_review.md
D9  artifact_inventory.csv
D10 compatibility/<route-id>/ for each tested route
D11 mlir_circt_stage_matrix.csv
D12 decision_matrix_scored.csv
D13 corpus_flow.mmd
D14 route_family_comparison.md
D15 timeline.mmd
D16 final_report.md and final_report.pdf
```

The FPGA board remains unspecified. Generic synthesis can proceed, but final
placement, bandwidth, resource, timing, and performance claims wait for a fixed
board and part. The fixtures are completeness and state instruments, not
performance targets. No final level counts, sample, or route scores are
published until scripts run against all 461 records and adjudication completes.
