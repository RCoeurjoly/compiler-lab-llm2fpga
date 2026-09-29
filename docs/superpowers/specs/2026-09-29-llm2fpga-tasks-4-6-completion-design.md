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

The original written task calls for a survey of 5–10 mitigation strategies at
model, compiler/MLIR, or RTL level. The user now sets an outcome-based stopping
rule: do not treat five as a minimum number of new experiments. If one or two
distinct, measured strategies achieve correct board fit for the Task 6 baseline,
stop optimization experiments and report those results. This is an explicit
revision to the original 5–10-strategy requirement, not a claim that the
original text already permits early completion. Existing additional strategies
may be surveyed and reported without new runs; do not invent five evaluations.
For strategies actually evaluated, compare against the baseline and record
LUT/FF/BRAM/DSP, maximum-frequency, toolchain-runtime and peak-memory deltas
where available. Negative and neutral results are valid evidence. Successful
strategies must not depend on operator stubs or hidden blackboxes.

First inventory existing optimizations and recover comparable measurements.
Do not reimplement an optimization merely to recreate its history. Identify
missing evidence and new experiments only after that audit. Evaluate additional
strategies only while the board-fit stopping condition remains unmet; do not
keep adding candidates indefinitely.

Treat Task 6 primarily as consolidation of existing experiments and reporting,
not a new optimization-development project. The corrected quantization strategy
is a central candidate: compare the earlier Task 3 numerical representation
with the corrected profile, documenting correctness as well as resource,
timing, runtime and peak-memory differences. If quantization enables correct
BRAM-resident inference for the Task 6 baseline, stop optimization experiments
and document the measured outcome; DDR3 is not required to demonstrate it.

Report any existing DDR3 externalization evaluation as a resource-reduction
alternative, with integration failures and unverified hardware results stated
explicitly. A negative result is valid evidence; working DDR3 inference is not
a Task 6 completion gate. Preserve its existing evidence without reopening the
deferred integration effort solely for this survey.

Compiler-pipeline changes may provide distinct strategies if more experiments
are needed to achieve board fit. Using Calyx alone is an architectural
choice, not evidence of resource reduction. Count concrete techniques separately
only when their mechanisms and experimental evidence are distinguishable: for
example, compute-unit sharing, memory banking/mapping, or request-controller
consolidation. These are inventory candidates, not assertions that each has
already been evaluated. Do not split one change into several strategy labels.
Reuse comparable existing measurements, mark missing comparisons, and
perform only the bounded experiments needed to establish the outcome or explain
why it remains unmet.

Deliver a strategy survey, reproducible usage scripts for strategies actually
evaluated, before/after resource reports, and a comparison table with available
deltas and viability status. State the early-stop decision and its evidence.
Distinguish semantic corrections and tool compatibility fixes from resource
optimizations.
Do not describe a failed or semantically mismatching strategy as a viable
resource reduction. Any deliberately different numerical profile needs its own
disclosed reference; it cannot silently replace the Task 4 fixed-point contract.

The plan requires the largest successfully lowered model from Task 5 as the
baseline. Begin with the currently evidenced 1M model, but label the Task 6
baseline provisional until the Task 5 matrix establishes that largest model.
If a larger model is lowered, check whether the claimed board-fit outcome holds
for that baseline; otherwise report the 1M result as a narrower achievement,
not Task 6 completion. The priority order does not waive this dependency.

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

Before marking Tasks 4–6 complete, map every applicable deliverable to committed
sources, a reproducible command, and inspected results. Record the Task 6
early-stop revision alongside the original plan, and resolve missing artifacts,
incomparable optimization baselines, unsupported functional claims, and the
Task 6/Task 5 baseline dependency. Publish limitations and failed cases.

This spec approves neither task completion nor external submission. The next
step is written-spec review, then an implementation plan led by evidence
inventory and gap closure. The old DDR3 goal is not silently resumed or marked
complete; replace it explicitly when the revised execution goal is established.
