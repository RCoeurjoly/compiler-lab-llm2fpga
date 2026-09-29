# TinyStories-1M Task 6 Fit Evidence Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish and report whether the existing compiler-generated TinyStories-1M implementation has already met Task 6's FPGA-fit objective, without launching new optimization experiments.

**Architecture:** Audit the committed compiler path, production implementation report and programmed-board receipt as separate evidence layers. Then publish Task 6's strategy survey and before/after comparison, explicitly distinguishing measured results, incomparable historical baselines and missing metrics. Task 4 hardware deliverables and Task 5 scaling are independent follow-up plans, not gates on this Task 6 closure.

**Tech Stack:** Nix, Yosys, nextpnr-xilinx, Kintex-7, SystemVerilog, Org/Markdown, Git.

**Spec:** `docs/superpowers/specs/2026-09-29-llm2fpga-tasks-4-6-completion-design.md`

## Global Constraints

- TinyStories-1M is the Task 6 fit target; later Task 5 models do not reopen Task 6. Record this explicit revision to `docs/project-plan_v2.org`.
- Preserve the authenticated model, fixed-point contract, compiler-generated accelerator, 30 MHz on-chip implementation and passing board artifacts. Kev-gpt is a reference oracle only.
- An implementation that fits and is functionally valid stops the strategy search, even if fewer than five strategies were evaluated. Do not reopen DDR3 or PCIe integration for Task 6.
- Do not treat a raw synthesis cell count, an RC result or a Nix store path alone as full-model board-fit evidence. Keep unresolved BRAM/DSP timing coverage visible.
- Commit authoritative recipes and reports. Nix retains large build outputs; `/tmp` and ignored scratch files are not reproducibility sources.
- The approved execution of this plan should provide standing authority to commit accurately labeled **diagnostic** checkpoints for failed evidence checks, because `.agents/AGENTS.md` otherwise requires a separate approval for each such commit. Such a commit must not claim fit or task completion. No destructive cleanup or board programming is authorized by this plan.

## Review Focus

1. RC or handwritten accelerator evidence substituted for the compiler-generated full 1M design: reject at Task 1 source-closure check.
2. Synthesis fits but routing/board implementation does not: reject at Task 1 production-report and bitstream check.
3. Numeric profile or model image differs from the authenticated board run: disclose and reject equivalence at Task 1 identity check.
4. Accepted bitstream works but its recipe depends on uncommitted scratch or vanished store paths: record a reproducibility gap at Task 1 rebuild-source check.
5. Reported 30 MHz success is mistaken for complete timing coverage: retain the BRAM/DSP caveat at Task 2 report review.

---

### Task 1: Audit the existing TinyStories-1M FPGA-fit claim

**Files:**
- Read: `docs/results/2026-09-29-compiler-full16-bram-board-acceptance.md`
- Read: `docs/results/2026-09-28-ramb36-odd-width-configuration.md`
- Read: `docs/superpowers/specs/2026-09-29-llm2fpga-tasks-4-6-completion-design.md`
- Create: `docs/results/2026-09-29-task6-fit-audit.md`

**Interfaces:**
- Consumes: the accepted full16 bitstream, production resource/route reports, Nix derivations, programming receipt, raw token exchanges, compiler-source closure and frozen reference named in the acceptance report.
- Produces: a claim-by-claim audit with `verified`, `missing` or `incomparable` status and exact evidence paths/commands for Task 2.

- [ ] **Step 1: Check the board receipt against the claimed result.** Inspect `/nix/store/lgh6ymv5fnsrybqpk8z1apxlm45845j3-compiler-full16-three-sram-board-evidence/verification.json` and its raw archive. Confirm three independently programmed SRAM runs, 16 exact tokens, one START per run, four host prompt writes and no host-fed generated tokens. A missing artifact is a gap, not a passed check.
- [ ] **Step 2: Check identity and physical fit.** Run `sha256sum /nix/store/mb1678v9k8cxwwrzsj9brzcms31b6v27-compiler-full16-two-rom-qualified-mode-checked-bitstream/model.bit`; expected digest `bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f`. Inspect the production synthesis/route report behind the acceptance document: 813 RAMB36E1, 89 RAMB18E1, 9,688 RAM64M, 190 DSP48E1, zero route overuse/architecture failures, and covered 55.08 MHz versus 30 MHz. Verify model/reference identity and compiler ownership; do not infer full timing qualification.
- [ ] **Step 3: Check source reproducibility.** Trace the bitstream and board-archive derivations back to committed Nix expressions and compiler sources. Record the exact build command and pinned inputs if found. If any recipe exists only in ignored scratch or refers to unavailable inputs, mark that part `missing` and plan the smallest source-closure repair rather than silently blessing the store output.
- [ ] **Step 4: Write the audit.** In `docs/results/2026-09-29-task6-fit-audit.md`, separate the measured FPGA-fit outcome from Task 4 inference and timing-coverage claims; state any remaining evidence gaps. Compare all five Review Focus cases explicitly.
- [ ] **Step 5: Verify and commit.** Run `git diff --check`, re-open every cited receipt/report, and compare the audit's numbers and hashes to the originals. Commit the verified audit immediately. If a required check fails, stop the success claim; a diagnostic-only commit is allowed only under the standing authority in the approved plan.

### Task 2: Publish the Task 6 strategy and completion report

**Files:**
- Create: `resource_usage_reduction_strategies.org`
- Read: `docs/adr/2026-07-10-validated-optimization-progress.md`
- Read: `docs/results/2026-09-29-task6-fit-audit.md`
- Read: `docs/project-plan_v2.org`

**Interfaces:**
- Consumes: Task 1's audited claim statuses and the existing quantization, memory-mapping, pipeline and DDR3 experiment records.
- Produces: Task 6 deliverables 6a–6c: strategy survey, usage/reproduction references, and before/after comparison with viability status.

- [ ] **Step 1: Inventory only genuinely distinct existing strategies.** Include corrected quantization and any evidenced compiler memory/compute restructuring; classify DDR3 externalization as an evaluated alternative only if an actual comparable experiment exists. Calyx adoption alone and compatibility/semantic fixes are not resource strategies.
- [ ] **Step 2: Build the before/after table.** For each strategy actually evaluated, record baseline/variant identities, model/quantization contract, LUT/FF/BRAM/DSP, Fmax, runtime and peak memory when measured. Mark missing or incomparable fields literally; do not combine incompatible reports into a fabricated delta. Link committed recipes or add the smallest missing in-repo recipe needed to reproduce an accepted comparison.
- [ ] **Step 3: State the stop outcome.** If Task 1 verifies a functionally valid full-1M fit, state that Task 6's engineering objective is met and no five-strategy campaign is needed. Document the explicit 1M-baseline and early-success deviations from the original project plan. Otherwise report the evidence gap and keep the bounded 5–10-strategy unsuccessful-search rule; do not call Task 6 complete.
- [ ] **Step 4: Verify and commit.** Re-read every table row against its cited primary report/receipt, check each reproduction command is committed or explicitly unavailable, run `git diff --check`, and commit the report and any necessary source-closure recipe. If verification fails, label a diagnostic checkpoint under the plan's standing authority; do not claim completion.

## Handoff

After Task 6 evidence closure, write separate Task 4 and Task 5 plans against the same approved spec. Do not start new accelerator or DDR3 work merely because the earlier goals contained it. A Task 4 plan audits/packages the existing full16 board result; a Task 5 plan measures the five TinyStories sizes and records the first failing stage for each.
