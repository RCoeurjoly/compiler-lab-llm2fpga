# RC Synthesis Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and commit durable mapped-Yosys and nextpnr-xilinx evidence for the functionally validated RC on Kintex-7 `xc7k480tffg1156-1`, including fit or exact failure boundaries before DDR3 integration.

**Architecture:** Reuse the receipt-verified normalized synthesis copy in `/tmp`, complete `synth_xilinx` to a mapped JSON, then feed that exact JSON to the pinned task3-main/openXC7 nextpnr-xilinx tool and Kintex-7 chip database. Keep verbose outputs outside Git in `/tmp`; commit a concise report containing provenance, commands, resource/timing evidence, runtime, peak RSS, critical paths, and any resource-limit failure.

**Tech Stack:** Yosys 0.66 with Slang plugin, `synth_xilinx -family xc7`, nextpnr-xilinx/openXC7, GNU `/usr/bin/time`, JSON, Markdown.

## Global Constraints

- Target only Kintex-7 `xc7k480tffg1156-1` with `xc7k480tffg1156.bin`.
- Preserve `TinyStories/rc_serving_direct_export.py` and `survey/` unchanged.
- Redirect verbose Yosys and nextpnr output to log files.
- Source closure: `/nix/store/5qm739maxpd9cvg5jwkdm316s8kr7g35-tinystories-w8a8-rc-polynomial-exp-calyx-native-sv-no-synthesis`.
- Functional source SHA-256: `2262298433271af636683517bba9c7641d02097de314b3dac4f4e3c0843e83f7`.
- Do not claim completion without actual mapped utilization and nextpnr timing evidence; a nextpnr failure report must quote the exact stage/resource limit and retain any timing evidence emitted before failure.
- Commit every repository change.

---

### Task 1: Complete mapped Yosys synthesis

**Files:**
- Consume: `/tmp/rc-main-synth-final.sv`
- Consume: `/tmp/rc-synth-receipt-final.json`
- Consume: `/tmp/rc-yosys-xc7-final.ys`
- Produce: `/tmp/rc-yosys-xc7-final.log`
- Produce: `/tmp/rc-yosys-xc7-final.time`
- Produce: `/tmp/rc-yosys-mapped-stat-final.json`
- Produce: `/tmp/rc-yosys-mapped-final.json`

**Interfaces:**
- Consumes: normalized top module `main` whose SHA-256 equals the receipt `output_sv_sha256`.
- Produces: fully mapped Xilinx JSON and Yosys mapped cell/resource statistics.

- [ ] **Step 1: Verify immutable inputs and available host resources**

Run `sha256sum /tmp/rc-main-synth-final.sv`, inspect the receipt, confirm the Yosys script names top `main`, and record `free -h` plus `df -h /tmp`.

- [ ] **Step 2: Run mapped synthesis with bounded logging and resource accounting**

Run `/usr/bin/time -v -o /tmp/rc-yosys-xc7-final.time <pinned-yosys> -ql /tmp/rc-yosys-xc7-final.log -s /tmp/rc-yosys-xc7-final.ys`. Do not stream the log.

- [ ] **Step 3: Verify mapped evidence**

Require a nonempty `/tmp/rc-yosys-mapped-final.json`, parse `/tmp/rc-yosys-mapped-stat-final.json`, and extract LUT, FF, BRAM, DSP, elapsed time, and maximum resident set size. If Yosys fails, record its exit status, final completed pass, exact diagnostic, elapsed time, and peak RSS.

### Task 2: Run nextpnr-xilinx on the mapped design

**Files:**
- Consume: `/tmp/rc-yosys-mapped-final.json`
- Produce: `/tmp/rc-nextpnr-xc7-final.log`
- Produce: `/tmp/rc-nextpnr-xc7-final.time`
- Produce when possible: `/tmp/rc-nextpnr-xc7-final.fasm`

**Interfaces:**
- Consumes: the exact mapped JSON from Task 1 and pinned `xc7k480tffg1156.bin` chipdb.
- Produces: placed/routed utilization, timing summary and critical-path diagnostics, or an exact stage/resource-limit failure.

- [ ] **Step 1: Resolve and record pinned backend provenance**

Locate the task3-main/openXC7 `nextpnr-xilinx` executable and `xc7k480tffg1156.bin`, then capture executable/chipdb paths, source revision, and tool version.

- [ ] **Step 2: Run nextpnr with resource accounting**

Run `/usr/bin/time -v -o /tmp/rc-nextpnr-xc7-final.time nextpnr-xilinx --chipdb <xc7k480tffg1156.bin> --json /tmp/rc-yosys-mapped-final.json --fasm /tmp/rc-nextpnr-xc7-final.fasm --xdc <probe-or-empty-xdc> --freq 12`, redirecting stdout and stderr together to `/tmp/rc-nextpnr-xc7-final.log`.

- [ ] **Step 3: Extract implementation evidence**

Record nextpnr exit status; LUT, FF, RAMB18E1/RAMB36E1, DSP48E1 used/available; timing/frequency; named critical paths; elapsed time; peak RSS; and any packing, placement, routing, timing, or resource-limit failure. Preserve evidence even if no FASM is emitted.

### Task 3: Publish and commit the baseline report

**Files:**
- Create: `docs/results/2026-08-10-rc-synthesis-baseline.md`
- Modify: `docs/superpowers/plans/2026-08-10-rc-synthesis-baseline.md`

**Interfaces:**
- Consumes: receipt, Yosys statistics/log/time, nextpnr log/time, and tool provenance.
- Produces: durable statement of what fits before DDR3 integration, with bounded claims.

- [ ] **Step 1: Write the evidence report**

Include source hashes and functional-validation scope, normalizer receipt, exact commands and tool versions, mapped utilization versus XC7K480T capacity, nextpnr utilization/timing/critical paths, runtimes/peak RSS, failure frontier, and the explicit pre-DDR3 fit conclusion.

- [ ] **Step 2: Verify every quantitative claim against raw evidence**

Re-run parsers/checks over the JSON/log/time files, confirm the report has actual mapped utilization and nextpnr timing evidence, and inspect `git diff --check` plus `git diff -- docs/superpowers/plans/2026-08-10-rc-synthesis-baseline.md docs/results/2026-08-10-rc-synthesis-baseline.md`.

- [ ] **Step 3: Preserve unrelated changes and commit only task files**

Run `git status --short`, stage only the plan and report, confirm `TinyStories/rc_serving_direct_export.py` and `survey/` remain unstaged, and commit with message `docs: record RC xc7k480t synthesis baseline`.
