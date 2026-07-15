# Calyx Native-SV Regression Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a valid integer native-Calyx SystemVerilog source list under the pinned upstream Calyx package, and make the repository’s current-baseline documentation match the verified full W8A8 frontier.

**Architecture:** Native Calyx/Morty now emits the imported integer and float primitive closure into `main.sv`. The native-SV exporter must therefore give downstream Yosys only that generated file, for both integer and float Futil. A new small integer Nix self-test will prove the closure, while the existing full-model evidence remains a native-SV-generation frontier with no mapped FPGA result. Historical baseline results remain preserved but are explicitly scoped to the pre-current-source-pin environment.

**Tech Stack:** Nix flakes, pinned Calyx 0.7.1 package from upstream source, HardFloat, Calyx Futil, Bash, Python `unittest`, `yosys-slang`.

## Global Constraints

- Preserve Calyx revision `5a4303847392609cad83dda6f4bdffc8cc0e5c89`, the `pkgsLlvm21` package scope, and HardFloat `sha256-azdXyfv6IjDGorhGBeOTcstYnddQDpecTwuOzIoDsUs=`.
- Keep the full W8A8 conclusion bounded: it reached Calyx/Futil output and was killed during native SV emission; no full-model SV, Yosys, mapping, LUT/FF/BRAM/DSP, nextpnr, board, equivalence, or SmoothQuant claim may be added.
- Work on user-approved `main`; do not alter the pre-existing `docs/glossary.md` modification.
- Do not run garbage collection, delete Nix store paths, or rerun the full TinyStories native-SV build merely for this remediation.
- Use test-first development for the exporter behavior change; observe the regression test fail before changing production exporter/Nix code.
- All durable artifacts and tests belong in the repository/Nix derivations, not `/tmp`.

---

### Task 1: Make native Calyx `main.sv` the uniform integer and float closure

**Files:**

- Create: `reproducers/calyx-integer-library-selftest/input.futil`
- Create: `reproducers/calyx-integer-library-selftest/README.md`
- Modify: `tests/test_calyx_float_nix_package.py`
- Modify: `flake.nix`
- Modify: `scripts/pipeline/calyx_to_sv_no_handshake.sh`
- Modify: `nix/pipeline.nix`
- Modify: `tests/test_representative_core_no_handshake_sv.py`
- Delete: `scripts/pipeline/calyx_compile_primitives_to_sv.py`

**Interfaces:**

- Consumes: `calyx_to_sv_no_handshake.sh` receives native Calyx’s `$output_dir/sv/main.sv` after `calyx -b verilog --synthesis --nested -d papercut`.
- Produces: `$output_dir/sources.f` containing exactly `$output_dir/sv/main.sv`, for every native-Calyx Futil route.
- Produces: `.#calyx-integer-library-selftest`, whose `sources.f` and `yosys-slang.log` prove a real integer primitive closure.

- [ ] **Step 1: Add failing static contracts and an integer Futil fixture**

  Add `reproducers/calyx-integer-library-selftest/input.futil`:

  ```futil
  import "primitives/core.futil";

component main(@go go: 1) -> (@done done: 1) {
  cells {
    add = std_add(32);
    result = std_reg(32);
  }
  wires {
    group add_constants {
      add.left = 32'd1;
      add.right = 32'd2;
      result.in = add.out;
      result.write_en = 1'd1;
      add_constants[done] = result.done;
    }
  }
    control { seq { add_constants; } }
  }
  ```

  Add a README that says this is a native-Calyx/Yosys source-closure test, not numerical-equivalence evidence. Extend `CalyxFloatNixPackageTest` so it requires the new fixture, `calyxIntegerLibrarySelftest`, a `calyx-integer-library` package/check alias, and a script source list that contains only `main.sv` and no legacy primitive/generator branch.

- [ ] **Step 2: Run the focused contract test and observe RED**

  Run:

  ```bash
  python3 -m unittest tests.test_calyx_float_nix_package.CalyxFloatNixPackageTest -v
  ```

  Expected: failure because the integer self-test is not yet declared and the exporter still contains `uses_float_extern` plus the legacy five-file closure.

- [ ] **Step 3: Add the native integer Nix self-test**

  In `flake.nix`, mirror `calyxFloatLibrarySelftest` with `calyxIntegerLibrarySelftest`. It must run the pinned `calyx` on the new Futil, write `main.sv`, assert it contains both `module std_add` and `module std_reg` with a whitespace-aware Python regex, write a one-line `sources.f`, then invoke `yosys-slang` with:

  ```text
  read_slang --threads 1 --no-proc --max-parse-depth 20000 --top main $out/main.sv
  hierarchy -top main -check
  ```

  Export the result under both `packages."calyx-integer-library-selftest"` and `checks."calyx-integer-library"`.

- [ ] **Step 4: Replace the obsolete file-list branch**

  In `calyx_to_sv_no_handshake.sh`, retain imported-Futil path validation but remove `uses_float_extern`, `CALYX_COMPILE_PRIMITIVES_TO_SV`, compilation of `compile.futil`, and the conditional five-file list. After successful native Calyx Verilog emission, write exactly:

  ```bash
  printf '%s\n' "$output_dir/sv/main.sv" >"$output_dir/sources.f"
  ```

  Remove the no-longer-used environment export in `nix/pipeline.nix`, remove static tests requiring legacy primitive files, and delete the unreferenced primitive-generation helper.

- [ ] **Step 5: Run GREEN verification**

  Run:

  ```bash
  python3 -m unittest tests.test_calyx_float_nix_package tests.test_representative_core_no_handshake_sv -v
  nix build .#calyx-float-library-selftest -L
  nix build .#calyx-integer-library-selftest -L
  nix build .#tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-yosys-stat -L
  git diff --check
  ```

  Expected: contracts pass; both self-tests pass `yosys-slang`; the small integer downstream route reaches its Yosys statistic; no duplicate-module error occurs.

- [ ] **Step 6: Commit Task 1**

  ```bash
  git add flake.nix nix/pipeline.nix scripts/pipeline/calyx_to_sv_no_handshake.sh \
    scripts/pipeline/calyx_compile_primitives_to_sv.py \
    reproducers/calyx-integer-library-selftest tests/test_calyx_float_nix_package.py \
    tests/test_representative_core_no_handshake_sv.py
  git commit -m "fix: use native Calyx SV closure for integer routes"
  ```

### Task 2: Mark superseded Calyx observations as historical and state the real current frontier

**Files:**

- Modify: `docs/current-baseline.md`
- Modify: `tests/test_task3_pinned_w8a8_utilization.py`
- Modify: `tests/test_pipeline_clarity.py`
- Modify: `tests/test_representative_core_no_handshake_sv.py`

**Interfaces:**

- Consumes: the verified self-tests and `docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md`.
- Produces: a baseline document that distinguishes current pinned-source facts from retained pre-pin historical data.

- [ ] **Step 1: Add failing documentation contracts**

  Require the baseline to state all of the following:

  ```text
  native Calyx was killed during SV emission
  5a4303847392609cad83dda6f4bdffc8cc0e5c89
  historical / pre-current-source-pin
  ```

  Require the fixed-LayerNorm missing-float-import discussion to be explicitly historical, and make the existing representative-core baseline test require a pending-rerun qualifier instead of calling the results current reproducible output.

- [ ] **Step 2: Run documentation tests and observe RED**

  Run:

  ```bash
  python3 -m unittest \
    tests.test_task3_pinned_w8a8_utilization \
    tests.test_pipeline_clarity \
    tests.test_representative_core_no_handshake_sv -v
  ```

  Expected: failures because the baseline still names missing float primitives as the current cause and calls old results current/reproducible.

- [ ] **Step 3: Correct the baseline without deleting historical evidence**

  Update the lead W8A8 section to say the package-level float closure succeeds, the full route produces Futil, and native Calyx is killed during SV emission. Change source provenance from the crates.io package wording to pinned upstream Calyx at the exact revision with package version `0.7.1` only as a package-version label.

  Prefix the old native integer resource tables, fixed-LayerNorm float diagnosis, explicit-integer slice, and equivalence snapshot with clear historical/pre-current-source-pin and pending-rerun scope. Preserve prior numbers as archival observations; do not claim they reproduce under the repaired source-list path until Task 1’s relevant routes have actually rerun.

- [ ] **Step 4: Run GREEN verification**

  Run:

  ```bash
  python3 -m unittest \
    tests.test_task3_pinned_w8a8_utilization \
    tests.test_pipeline_clarity \
    tests.test_representative_core_no_handshake_sv -v
  git diff --check
  ```

  Expected: all documentation contracts pass and the baseline makes no missing-library claim for the current full W8A8 frontier.

- [ ] **Step 5: Commit Task 2**

  ```bash
  git add docs/current-baseline.md tests/test_task3_pinned_w8a8_utilization.py \
    tests/test_pipeline_clarity.py tests/test_representative_core_no_handshake_sv.py
  git commit -m "docs: scope historical Calyx baseline results"
  ```

### Task 3: Re-review and final verification

**Files:**

- Modify: `.superpowers/sdd/progress.md` (ignored execution ledger only)

**Interfaces:**

- Consumes: Task 1’s behavioral source-list proof and Task 2’s corrected baseline.
- Produces: a reviewed main branch with evidence-backed conclusions only.

- [ ] **Step 1: Review each task and the combined range**

  Generate review packages from the commit before Task 1 to each task head, then from that same base through Task 2. Require reviewers to check that `sources.f` is main-only for both self-tests, the downstream integer route ingests it successfully, and historical documentation does not masquerade as a rerun.

- [ ] **Step 2: Run final verification**

  Run:

  ```bash
  python3 -m unittest \
    tests.test_calyx_float_nix_package \
    tests.test_representative_core_no_handshake_sv \
    tests.test_task3_pinned_w8a8_utilization \
    tests.test_pipeline_clarity -v
  nix build .#calyx-float-library-selftest -L
  nix build .#calyx-integer-library-selftest -L
  nix flake check -L
  git diff --check
  ```

  Expected: all selected tests pass (with only the documented PyTorch-dependent skip), both native closure self-tests build, flake checks pass, and no unintended worktree change beyond the user-owned glossary edit exists.

- [ ] **Step 3: Commit execution ledger only if needed**

  Do not add `.superpowers/` files unless the repository’s ignore policy is deliberately changed. The user-facing commits are Task 1 and Task 2; leave the user-owned glossary edit unstaged.

## Plan self-review

- **Spec coverage:** Task 1 covers the demonstrated duplicate-module regression with a new behavioral integer closure test and a real downstream Yosys route. Task 2 covers every stale baseline area identified by review without deleting archival evidence. Task 3 makes review and verification explicit.
- **Placeholder scan:** no TBD/TODO placeholders; each code-bearing task lists concrete paths, source-list behavior, commands, and expected outcome.
- **Interface consistency:** Task 1 produces the `sources.f` main-only contract consumed by existing `mkIlDerivation`/`mkYosysStatDerivation`; Task 2 only changes interpretation of historical evidence; Task 3 verifies both.

## Execution

The user previously selected subagent-driven execution for this workstream. Continue with `superpowers:subagent-driven-development` on the approved `main` tree.
