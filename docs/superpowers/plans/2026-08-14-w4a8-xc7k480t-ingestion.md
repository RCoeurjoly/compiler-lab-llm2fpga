# W4A8 XC7K480T Ingestion Implementation Plan

> **Outcome:** Superseded after the prefill-8 phase-only diagnostic. Prefill
> mapped successfully but required 131% of XC7K480T LUT capacity in nextpnr.
> Decode synthesis was cancelled when review established that the three
> verified closures are independent shape-specialized engines, not one
> stateful RTL instance. See
> `docs/results/2026-08-14-w4a8-prefill-xc7k480t-diagnostic.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible mapped-Yosys and nextpnr-xilinx evidence that says whether each verified W4A8 phase fits Kintex-7 `xc7k480tffg1156-1` before DDR3 integration.

**Architecture:** Add one parameterized Nix evidence pipeline that consumes each canonical native-Calyx SV closure directly, applies the existing synthesis-only frontend normalizer with a receipt, runs mapped `synth_xilinx`, and conditionally feeds successful mapped JSON through the established distributed-RAM compatibility map and pinned openXC7 nextpnr. Every stage retains compressed logs, exit status, GNU time data, hashes, and a compact JSON receipt even when a tool fails.

**Tech Stack:** Nix, Yosys 0.66 with yosys-slang, `synth_xilinx -family xc7`, pinned task3-main nextpnr-xilinx/openXC7, `xc7k480tffg1156.bin`, Python `unittest`, JSON, Markdown.

## Global Constraints

- Target only Kintex-7 `xc7k480tffg1156-1` with `xc7k480tffg1156.bin`.
- Consume the verified prefill-8, decode-8, and decode-9 immutable Nix SV closures; do not copy canonical inputs through `/tmp`.
- Redirect verbose Yosys and nextpnr output to retained compressed log files.
- Record mapped LUT, FF, BRAM, DSP, total cells, runtime, and peak RSS for every phase that maps.
- Record nextpnr resource use, timing/Fmax, critical paths, runtime, peak RSS, and the exact failure stage for every phase attempted.
- A failed mapped or P&R stage is evidence, not a reason for the evidence derivation itself to discard its output.
- Do not perform formal verification, manual RTL optimization, DDR3 integration, or board bring-up.
- Commit every repository change and preserve unrelated user files.

---

### Task 1: Define the durable three-phase evidence pipeline

**Files:**
- Create: `nix/rc-serving-w4a8-xc7k480t.nix`
- Create: `scripts/pipeline/write_w4a8_xc7_evidence.py`
- Create: `tests/test_rc_serving_w4a8_xc7k480t.py`
- Modify: `flake.nix`

**Interfaces:**
- Consumes: `{ phaseName, nativeSv }`, the existing synthesis normalizer, pinned Yosys/yosys-slang, nextpnr, and XC7K480T chipdb.
- Produces: one Nix output per phase containing `result.json`, source and normalized hashes, normalization receipt, Yosys and nextpnr status/time/log files, mapped statistics/JSON when available, and FASM when P&R succeeds.

- [ ] **Step 1: Write failing source-contract and evidence-parser tests**

Assert that all three phase package names are exported, each consumes the corresponding `*-calyx-native-sv` closure, the target/chipdb are exact, both tools are resource-accounted and log-redirected, and failures are preserved in `result.json`. Add parser fixtures for mapped success, Yosys failure, nextpnr success, and over-capacity nextpnr failure.

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run `python3 -m unittest tests.test_rc_serving_w4a8_xc7k480t -v`. Expected: failure because the new Nix module, parser, and flake exports do not exist.

- [ ] **Step 3: Implement the evidence parser and Nix derivation**

The parser accepts phase/provenance paths plus optional Yosys stat, Yosys/nextpnr statuses, logs, and time files. It emits schema `llm2fpga.w4a8-xc7k480t-evidence.v1`, normalized resource categories, timing status, failure stage/diagnostic, and a fit decision that can only be `fits`, `does-not-fit`, or `undetermined` according to actual mapped/P&R evidence.

The Nix derivation must always retain evidence after a tool invocation. It runs nextpnr only when mapped JSON exists, records `not-run` with the Yosys reason otherwise, and uses the existing RAM64X1S/RAM128X1S compatibility transform before nextpnr when those unsupported primitives occur.

- [ ] **Step 4: Export and instantiate all three phases in `flake.nix`**

Export:

```text
tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-xc7k480t-evidence
tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-xc7k480t-evidence
tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-9-xc7k480t-evidence
```

- [ ] **Step 5: Run focused tests and evaluate the package surface**

Run `python3 -m unittest tests.test_rc_serving_w4a8_xc7k480t -v` and `nix eval .#packages.x86_64-linux --apply builtins.attrNames --json`. Require all tests to pass and all three package names to appear.

- [ ] **Step 6: Commit the reproducible ingestion path**

Stage only the four task files and commit with `feat: add W4A8 XC7K480T evidence pipeline`.

### Task 2: Build and audit actual mapped/P&R evidence

**Files:**
- Consume: the three package outputs from Task 1.
- Produce: immutable Nix outputs containing raw and parsed evidence.

**Interfaces:**
- Consumes: exact verified SV closures whose hashes are recorded in `docs/results/2026-08-14-w4a8-three-phase-equivalence.json`.
- Produces: actual per-phase mapped/P&R results or exact durable tool/resource failure boundaries.

- [ ] **Step 1: Build prefill-8 evidence with bounded console output**

Run `nix build .#tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-xc7k480t-evidence --no-link --print-out-paths`, redirecting verbose output to a log file. Record wall time, peak RSS, and output path.

- [ ] **Step 2: Build decode-8 and decode-9 evidence**

Run the two equivalent package builds with separate redirected logs and time files. Do not infer one decode phase from the other.

- [ ] **Step 3: Audit every output against raw evidence**

Validate JSON syntax; source and normalized SV hashes; normalizer receipt; Yosys status/stat/log/time; mapped JSON hash if emitted; nextpnr status/resource/timing/log/time; and the parser's fit decision. Treat absent evidence as `undetermined`, never as fit.

### Task 3: Publish the fit report and machine-readable aggregate

**Files:**
- Create: `docs/results/2026-08-14-w4a8-xc7k480t-ingestion.md`
- Create: `docs/results/2026-08-14-w4a8-xc7k480t-ingestion.json`
- Modify: `docs/superpowers/plans/2026-08-14-w4a8-xc7k480t-ingestion.md`

**Interfaces:**
- Consumes: all three immutable evidence outputs and their raw retained artifacts.
- Produces: a reviewable per-phase utilization/timing table and an explicit overall pre-DDR3 fit conclusion.

- [ ] **Step 1: Write the report from actual evidence**

Record tool versions, chipdb identity/hash, closure paths/hashes, exact commands, LUT/FF/BRAM/DSP utilization and capacities, timing/Fmax and critical paths, tool and outer-build runtimes/peak RSS, failure stages, and per-phase plus overall fit decisions.

- [ ] **Step 2: Create the aggregate JSON receipt**

Copy quantitative facts from the immutable per-phase `result.json` files, include their Nix paths and SHA-256 hashes, and state limitations explicitly where timing or routing did not complete.

- [ ] **Step 3: Verify claims and regressions freshly**

Run the focused test module, JSON parsers, an independent script comparing every report number to the three Nix receipts, `git diff --check`, and inspect the complete diff. Do not claim timing when legal route did not complete.

- [ ] **Step 4: Commit the durable result**

Mark completed plan checkboxes, stage the plan and two reports, commit with `docs: record W4A8 XC7K480T ingestion`, and confirm the worktree is clean.
