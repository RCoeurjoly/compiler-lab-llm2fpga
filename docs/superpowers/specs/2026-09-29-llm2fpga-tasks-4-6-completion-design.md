# Finish LLM2FPGA Tasks 4–6 without expanding the completion boundary

## Agreed intent and authority

The user approved this scope on 2026-09-29: finish LLM2FPGA against the written
Tasks 4, 5 and 6, with working priority **6 → 4 → 5**. The source is
`/home/roland/LLM2FPGA/docs/project-plan_v2.org`; the requirements relevant to
this decision are restated below so this spec remains readable independently
of that local checkout. Approval of this scope is not a task-completion claim.

This supersedes the additional completion requirements in the previous
PCIe+UberDDR3 goal. DDR3 integration, PCIe migration, expanded CLI functionality,
variable-length prompts, configurable generation counts, and board inference
for every TinyStories size are follow-up work, not prerequisites for finishing
these tasks. Preserve their existing work and evidence; do not delete it.

The recently discussed 20-token variable-prompt workflow is also deferred.
Minimal host usability needed to reproduce the accepted hardware demonstration
remains in scope. No new transport, model architecture, or performance target
is introduced.

## Functional meaning and implementation requirements

Model inference is a complete model forward pass from input tokens to model
outputs. Autoregressive generation repeats inference using selected output
tokens as subsequent context. Task 4 specifies a fixed input and matching
hardware outputs; it does not require a general-purpose chat application.

Use the existing full-model, autonomous 16-token BRAM/LUTRAM demonstration as
the proposed Task 4 acceptance evidence, rather than replacing it with a weaker
kernel or first-token claim. The device must consume the initial prompt and
perform its own token feedback; the host must not supply generated tokens or
intermediate tensors. Expected answers belong only to the reference checker.

Preserve the authenticated TinyStories-1M model and fixed-point contract, the
compiler-generated implementation, and the existing 30 MHz on-chip baseline.
Kev-gpt remains an oracle only, not an accelerator RTL implementation source.
The implementation flow remains open-source EDA. Disclose LLM-assisted
provenance and unresolved BRAM/DSP timing coverage; functional success does not
establish full timing qualification or funding acceptance.

## Task 6: resource usage reduction strategies

The written task requires a survey of 5–10 mitigation strategies at model,
compiler/MLIR, or RTL level; evaluation of all selected strategies against a
baseline; and a conclusion about effectiveness and applicability. Required
measurements are LUT/FF/BRAM/DSP deltas, maximum-frequency deltas, and toolchain
runtime/peak-memory deltas. Negative and neutral results are acceptable.
Successful strategies must not depend on operator stubs or hidden blackboxes.

First inventory existing optimizations and recover comparable measurements.
Do not reimplement an optimization merely to recreate its history. Identify
missing evidence and new experiments only after that audit. Freeze the survey
set before evaluating it; do not keep adding candidates indefinitely.

Treat Task 6 primarily as consolidation of existing experiments and reporting,
not a new optimization-development project. The corrected quantization strategy
is a central candidate: compare the earlier Task 3 numerical representation
with the corrected profile, documenting correctness as well as resource,
timing, runtime and peak-memory differences. If quantization enables correct
BRAM-resident inference, DDR3 is not required to demonstrate that reduction;
this does not waive the remaining written survey and comparison deliverables.

Include DDR3 externalization as an evaluated resource-reduction alternative,
with its integration failures and unverified hardware results stated explicitly.
A negative result can satisfy a strategy evaluation; working DDR3 inference is
not a Task 6 completion gate. Preserve its existing evidence without reopening
the deferred integration effort solely for this survey.

Compiler-pipeline changes may provide the remaining distinct strategies needed
for the minimum five-strategy survey. Using Calyx alone is an architectural
choice, not evidence of resource reduction. Count concrete techniques separately
only when their mechanisms and experimental evidence are distinguishable: for
example, compute-unit sharing, memory banking/mapping, or request-controller
consolidation. These are inventory candidates, not assertions that each has
already been evaluated. Do not split one change into several labels to reach
five. Reuse comparable existing measurements, mark missing comparisons, and
perform only the bounded experiments needed to close identified evidence gaps.

Deliver the strategy survey, reproducible usage scripts, before/after resource
reports, and a comparison table with deltas and viability status. Distinguish
semantic corrections and tool compatibility fixes from resource optimizations.
Do not describe a failed or semantically mismatching strategy as a viable
resource reduction. Any deliberately different numerical profile needs its own
disclosed reference; it cannot silently replace the Task 4 fixed-point contract.

The plan requires the largest successfully lowered model from Task 5 as the
baseline. Begin with the currently evidenced 1M model, but label the Task 6
baseline provisional until the Task 5 matrix establishes that largest model.
Reconcile or rerun comparisons on a larger baseline if required. The priority
order does not waive this dependency or permit premature Task 6 completion.

## Task 4: FPGA integration and hardware validation

The written task requires a frozen host interface, an integrated synthesizable
model-plus-glue top, synthesis and PNR/resource reports, board execution of a
fixed input, and comparison with PyTorch. Deliver the interface specification,
top-level RTL, bitstream or PNR report, programming logs, reference/comparison
report, and short demonstration write-up.

Audit the recorded three-SRAM-reconfiguration 16-token on-chip result and bind
it to committed compiler sources and reproducible Nix builds. Record its actual
runtime, model/reference identity, programming evidence and timing limitations.
No task is declared complete merely because a receipt exists or says passed.

A small, finite set of additional four-token prompts is useful functional
confidence evidence and should use the same implementation if feasible. It is
not a requirement for new variable-length hardware or a broad prompt campaign.
If such a run exposes a mismatch, retain and localize it rather than concealing
it behind the frozen-prompt result. Do not claim unsupported prompt generality.

## Task 5: TinyStories scaling and resource usage analysis

The written scope is TinyStories 1M/3M/8M/28M/33M, excluding 1Layer-21M, with no
new model architectures. Deliver model metadata, per-model Nix derivations,
and a results matrix recording stage pass/fail, compile time, peak memory,
resource use and Fmax where available. Produce scaling plots, observed trends
and a bottleneck summary for each model's first failing stage.

A larger model failing lowering, exhausting host resources, or not fitting the
board is a legitimate measured result, not a reason to add DDR3 as an implicit
requirement. Retain reproducer evidence where practical. State unavailable
measurements explicitly; never invent downstream resource/timing numbers or
extrapolate TinyStories trends to unrelated families. Full-family board
inference is not the written acceptance criterion.

## Execution and evidence discipline

Keep authoritative source, configurations, tool patches, experiment recipes,
reference/checker definitions and reports in commits. Use Nix derivations for
generation, simulation and implementation, with explicit inputs and cached
stage boundaries. Keep large generated artifacts in Nix with retention roots
where necessary. `/tmp`, ignored scratch recipes and pre-existing store paths
alone are not the project's reproducible build definition.

The implementation plan should authorize a bounded sequence of in-scope
experiments and diagnostic checkpoints together, instead of seeking a fresh
design approval for each routine correction or sensible timebox adjustment.
An expected experiment failure is evidence, not successful production
verification. Record it accurately and preserve the passing baseline.
Repository commit rules still apply; necessary standing diagnostic-commit
authority must be explicit in the approved execution plan.

Use finite resource/time bounds informed by measurements. A bound may be
revised with a recorded justification; do not turn an arbitrary short limit
into a new project requirement. Do not restart a live job because it is quiet.
Ask for direction only for genuine scope changes, missing authority, security
or destructive operations outside existing approval, or an evidenced impasse.

OpenTPU and its experimental LiteDRAM work may inform the survey. They are not
new implementation dependencies or reasons to migrate the accepted accelerator.

## Completion audit and handoff

Before marking Tasks 4–6 complete, map every written deliverable to committed
sources, a reproducible command, and inspected results. Resolve missing
artifacts, incomparable optimization baselines, unsupported functional claims,
and the Task 6/Task 5 baseline dependency. Publish limitations and failed cases.

This spec approves neither task completion nor external submission. The next
step is written-spec review, then an implementation plan led by evidence
inventory and gap closure. The old DDR3 goal is not silently resumed or marked
complete; replace it explicitly when the revised execution goal is established.
