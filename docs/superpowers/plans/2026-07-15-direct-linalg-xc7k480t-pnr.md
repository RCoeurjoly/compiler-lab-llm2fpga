# Direct-Linalg XC7K480T Mapping and P&R Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task by
> task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Direct-Linalg no-handshake RTLIL into reproducible
XC7K480T mapped LUT/FF/BRAM/DSP estimates and an actual nextpnr-xilinx
pack/place/route utilization report.

**Architecture:** Reuse the nested Task 3 staged `synth_xilinx` mapper with
the Direct-Linalg `main` RTLIL.  A new nested-library P&R report helper routes
that mapped JSON through the pinned XC7 toolchain and retains its logs and
parsed device table.  The root flake supplies a probe-only XDC for the exact
core ports, so no wrapper changes the measured netlist.

**Tech stack:** Nix flakes, Yosys/yosys-slang, `synth_xilinx -family xc7`,
pinned nextpnr-xilinx, XC7K480T chip database, Python `unittest`.

## Global constraints

- Work on user-approved `main`; do not modify or stage the existing
  `docs/glossary.md` change.
- Target only `xc7k480tffg1156-1`, never an Artix device.
- Reuse the existing Direct-Linalg `.il` and top `main`; do not substitute the
  full W8A8 `main_1` route.
- Treat the route as resource/P&R evidence only, not functional equivalence,
  board validation, timing closure, or a full W8A8 result.
- Keep durable evidence in Nix outputs and repository files.  Do not run
  `nix gc`, delete store paths, or impose an arbitrary 40-minute cutoff.
- Test first for each behavior change, then run focused and end-to-end Nix
  verification.  If nextpnr fails, retain and document the failure frontier;
  do not claim utilization from a partial route.

### Task 1: Add a reusable nextpnr report derivation

**Files:**

- Create: `task3-main/scripts/pipeline/write_nextpnr_xilinx_report.py`
- Create: `tests/test_direct_linalg_xc7k480t_utilization.py`
- Modify: `task3-main/flake.nix`

**Interfaces:**

- Consumes: mapped Yosys JSON and XDC.
- Produces: an output directory with `nextpnr.log`, `stdout.log`, `stderr.log`,
  `route.json`, and `design.fasm` on successful P&R.
- Exports: `task3MainLib.mkTask3XilinxPnrReport`.

- [ ] **Step 1: Add failing parser and static Nix contracts**

  Add Python tests that require a schema-versioned report parser to preserve
  exit status/FASM status and parse a representative `Device utilisation`
  table.  Require the nested flake helper to use `--chipdb`, `--xdc`, `--json`,
  `--fasm`, and `--log`, and export it from `lib`.

- [ ] **Step 2: Observe RED**

  Run:

  ```bash
  python3 -m unittest tests.test_direct_linalg_xc7k480t_utilization -v
  ```

  Expected: parser/helper contracts fail because neither exists.

- [ ] **Step 3: Implement the frontier-preserving P&R helper**

  Add a Python parser and Nix helper.  The Nix builder must capture nextpnr
  logs and invoke the parser even if nextpnr exits nonzero.  Its JSON must
  distinguish an unsuccessful route from a successful routed FASM.

- [ ] **Step 4: Run GREEN verification and commit**

  ```bash
  python3 -m unittest tests.test_direct_linalg_xc7k480t_utilization -v
  git diff --check
  git add task3-main/flake.nix task3-main/scripts/pipeline/write_nextpnr_xilinx_report.py \
    tests/test_direct_linalg_xc7k480t_utilization.py
  git commit -m "feat: capture nextpnr xilinx utilization reports"
  ```

### Task 2: Wire the current Direct-Linalg core to XC7 mapping and P&R

**Files:**

- Modify: `flake.nix`
- Modify: `tests/test_direct_linalg_xc7k480t_utilization.py`

**Interfaces:**

- Consumes: the existing
  `tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-il`
  package and the Task 3 mapping/P&R library.
- Produces: root packages for mapped utilization, mapped JSON, probe XDC, and
  nextpnr utilization.

- [ ] **Step 1: Extend the test with failing root-wiring contracts**

  Require `modelIl` to reference the Direct-Linalg alias, `topName = "main"`,
  XC7K480T capacities, the four named port constraints, the exact mapped JSON
  handoff, and the public P&R package.

- [ ] **Step 2: Observe RED**

  Run the focused unit test.  Expected: root package contracts fail before the
  flake wiring exists.

- [ ] **Step 3: Implement root derivations**

  Add a named Direct-Linalg route bundle in `flake.nix`.  Its XDC must document
  that it is an implementation probe, use `AA28/R28/P30/M30` with `LVCMOS18`,
  and map `clk/reset/go/done` directly.  Export the staged mapper summary and
  JSON plus the P&R report package.

- [ ] **Step 4: Run GREEN verification and commit**

  ```bash
  python3 -m unittest tests.test_direct_linalg_xc7k480t_utilization -v
  nix flake check -L
  git diff --check
  git add flake.nix tests/test_direct_linalg_xc7k480t_utilization.py
  git commit -m "feat: route direct linalg core on xc7k480t"
  ```

### Task 3: Produce and record actual XC7K480T results

**Files:**

- Create: `docs/results/2026-07-15-direct-linalg-xc7k480t-pnr.md`
- Modify: `.superpowers/sdd/progress.md` (ignored execution ledger only)

**Interfaces:**

- Consumes: the mapped utilization and nextpnr packages from Task 2.
- Produces: checked-in evidence pointing to the exact commands, Nix outputs,
  mapper counts, and the nextpnr status/device table.

- [ ] **Step 1: Build the staged mapper**

  ```bash
  nix build .#tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-xc7k480t-mapped-utilization -L
  ```

  Inspect and preserve its `summary.json`, `summary.txt`, and mapped JSON path.

- [ ] **Step 2: Build nextpnr to a terminal report**

  ```bash
  nix build .#tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-xc7k480t-nextpnr-utilization -L
  ```

  Do not impose a short cutoff.  On success, verify zero exit status, FASM,
  and parsed device utilization.  On failure, capture the exact terminal
  frontier and logs, then diagnose and retry only with evidence-backed fixes.

- [ ] **Step 3: Write bounded results documentation**

  State the exact device, source derivation, mapper resource estimates, route
  status, and parsed nextpnr table.  Separate mapped estimates from actual
  placement/routing and explicitly exclude functionality/timing/board claims.

- [ ] **Step 4: Review, final verification, and commit**

  ```bash
  python3 -m unittest tests.test_direct_linalg_xc7k480t_utilization -v
  nix flake check -L
  git diff --check
  git add docs/results/2026-07-15-direct-linalg-xc7k480t-pnr.md
  git commit -m "docs: record direct linalg xc7k480t route"
  ```

  Independently review each task and the full range before reporting success.
