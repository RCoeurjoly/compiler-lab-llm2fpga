# W8A8 Calyx Task 3 Utilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Produce a reproducible provisional XC7K480T LUT, FF, DSP48E1, and BRAM estimate for the full TinyStories PT2E W8A8 TOSA/no-Handshake/Calyx kernel by using the original Task 3 pinned Yosys synthesis closure.

**Architecture:** Expose a small reusable API from the nested task3-main flake so the root flake invokes the exact Task 3 Yosys package, yosys-slang plugin, staged synthesis sequence, and utilization writer. Import the unchanged Calyx SystemVerilog source list with main_1 as the out-of-context top, retain its external-memory ports, and retain each Task 3 stage as an independently cacheable derivation. The normal final output is a compact evidence bundle; a first Task 3 failure is recorded as a frontier and is not bypassed with a different pass sequence.

**Tech Stack:** Nix flakes, the Task 3 pinned Yosys and yosys-slang inputs, SystemVerilog/slang import, RTLIL, Yosys synth_xilinx for XC7, Python 3 unittest, JSON, Markdown.

## Global Constraints

- Work on main, as already authorized by the user.
- The input route is exactly PyTorch PT2E W8A8 -> Torch-MLIR -> TOSA -> Linalg -> SCF -> Calyx -> native SystemVerilog -> Task 3 Xilinx synthesis.
- Use the generated sources.f from tinystories-w8a8-via-tosa-no-handshake-calyx-native-sv; do not reconstruct, edit, or selectively prune the SystemVerilog source set.
- Select main_1 directly. Its 12,802 ports, 115,933 port bits, and 2,133 logical external memories must remain an out-of-context interface; do not add a DDR3 controller or a testbench wrapper.
- Use the Task 3 nested flake pinned Yosys revision 4716f4410f1508cad384d2f8542ada9f61bb7339 and yosys-slang revision d82b0b163a725fc1a401fbb6b465cd862517ec1f. Record the resolved tool manifest in every result.
- Reuse the original Task 3 sequence without -flatten, -noshare, submod, changed stage order, a different Yosys package, or a root-flake reimplementation of the synthesis stages.
- Preserve giant RTLIL/JSON checkpoints in Nix build sandboxes and expose them as separately cacheable stage packages; commit only compact reports, manifests, and documentation.
- Do not impose a scout cutoff below 10,000 minutes. Use monitored builds and record an actual resource or OOM frontier if one occurs.
- Equivalence, DDR3 implementation, SmoothQuant, board integration, nextpnr placement/routing, and partitioned synthesis are out of scope.
- Do not activate the partitioned submod fallback in this work. A documented failure of the exact route is the stopping point and requires a separately approved plan.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| task3-main/flake.nix | Export the pinned Task 3 import and mapping constructors without changing their stage implementation. |
| flake.nix | Instantiate the W8A8 main_1 route with the exported Task 3 API and expose stage/result packages. |
| scripts/pipeline/verify_rtlil_top_interface.py | Check the imported RTLIL top interface and emit the compact interface manifest. |
| scripts/pipeline/write_task3_pinned_utilization_result.py | Produce a uniform mapped or frontier result.json from compact artifacts. |
| tests/test_task3_pinned_w8a8_utilization.py | Lock the selected toolchain, input boundary, package wiring, and evidence schemas. |
| docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md | Record the observed Task 3 outcome and interpretation. |
| artifacts/tinystories-w8a8-calyx-task3-utilization/ | Contain only compact committed output from the successful mapping or documented frontier. |
| docs/current-baseline.md | Point readers to the current W8A8 mapping outcome. |
| docs/adr/2026-07-13-calyx-memory-blackbox-diagnostic.md | Keep the prior partial structural observations while removing any claim that they are a final mapped fit result. |

### Task 1: Export the exact Task 3 import and mapping boundary

**Files:**

- Create: tests/test_task3_pinned_w8a8_utilization.py
- Modify: task3-main/flake.nix:276-563
- Modify: task3-main/flake.nix:844-852

**Interfaces:**

- Consumes: the existing nested-flake functions mkYosysRtlil, mkSynthJsonStages, and mkMappedJsonUtilizationReport; inputs yosys, yosys-slang, pkgs, and python.
- Produces:
  - task3MainLib.mkTask3RtlilFromSlangFilelist :: { name, svFilelist, topName, postReadCommands ? [ ], quiet ? false, memoryLimitKb ? null } -> derivation
  - task3MainLib.mkTask3XilinxUtilization :: { name, modelIl, topName, capacities, topSv ? null, quiet ? false, memoryLimitKb ? null } -> { stages, utilization, json }
  - task3MainLib.task3Toolchain.manifest :: derivation containing JSON.

- [ ] **Step 1: Write the failing export and pinning regression**

Create tests/test_task3_pinned_w8a8_utilization.py with this initial test class. The tests are source-contract tests: they ensure the root cannot silently fall back to its current Yosys 0.66 port.

```python
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class Task3PinnedW8A8UtilizationTest(unittest.TestCase):
    def test_nested_task3_flake_exports_pinned_import_and_mapping_api(self) -> None:
        flake = read("task3-main/flake.nix")

        for symbol in [
            "mkTask3RtlilFromSlangFilelist",
            "mkTask3XilinxUtilization",
            "task3Toolchain",
            "task3-yosys-toolchain.json",
            "yosys = yosysPkg;",
            "yosysSlang = yosysSlang;",
        ]:
            self.assertIn(symbol, flake)

        self.assertIn("read_slang --threads 1 --no-proc --max-parse-depth 20000", flake)
        self.assertIn("mkSynthJsonStages", flake)
        self.assertIn("stages = mkSynthJsonStages {", flake)
        self.assertIn("mkMappedJsonUtilizationReport", flake)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
```

Expected: FAIL because the nested flake has no public Task 3 import/mapping API.

- [ ] **Step 3: Add a source-list RTLIL importer to task3-main/flake.nix**

Immediately after mkYosysRtlil, add the following constructor. It is an input-boundary adapter only: it invokes the existing pinned tools, imports every non-comment file-list entry, validates the requested top, runs optional assertions, and writes the cacheable RTLIL checkpoint. It does not run synthesis commands itself.

```nix
        mkTask3RtlilFromSlangFilelist =
          { name, svFilelist, topName, postReadCommands ? [ ], quiet ? false
          , memoryLimitKb ? null }:
          pkgs.runCommand "${name}.il" { } ''
            {
              printf 'read_slang --threads 1 --no-proc --max-parse-depth 20000 --top %q' \
                ${topName}
              while IFS= read -r line; do
                if [ -z "''${line//[[:space:]]/}" ]; then
                  continue
                fi
                if [ "''${line#\#}" != "$line" ]; then
                  continue
                fi
                printf ' %q' "$line"
              done < ${svFilelist}
              printf '\n'
              printf '%s\n' "hierarchy -top ${topName} -check"
              printf '%s\n' "${builtins.concatStringsSep "\n" postReadCommands}"
              printf '%s\n' "write_rtlil $out"
            } > run.ys

            ${pkgs.lib.optionalString (memoryLimitKb != null) ''
              ulimit -v ${toString memoryLimitKb}
            ''}
            ${yosysPkg}/bin/yosys ${pkgs.lib.optionalString quiet "-q"} \
              -m ${yosysSlang}/share/yosys/plugins/slang.so -s run.ys

            if [ ! -e "$out" ]; then
              echo "mkTask3RtlilFromSlangFilelist did not create $out" >&2
              cat run.ys >&2
              exit 1
            fi
          '';
```

Keep mkYosysRtlil and all existing Stage 1 through Stage 9 implementations unchanged.

- [ ] **Step 4: Add the exact mapping wrapper and compact tool manifest**

Immediately after mkMappedJsonUtilizationReport, add the wrapper and manifest. The wrapper must call the existing Task 3 stages and existing report writer rather than copying their scripts or command strings.

```nix
        task3Toolchain = rec {
          manifest = pkgs.writeText "task3-yosys-toolchain.json"
            (builtins.toJSON {
              schema_version = 1;
              source = "task3-main";
              yosys = {
                source_rev = yosys.sourceInfo.rev;
                package_version = yosysPkg.version;
              };
              yosys_slang = {
                source_rev = inputs."yosys-slang".sourceInfo.rev;
                package_version = yosysSlang.version;
              };
            });
          yosys = yosysPkg;
          yosysSlang = yosysSlang;
        };

        mkTask3XilinxUtilization =
          { name, modelIl, topName, capacities, topSv ? null, quiet ? false
          , memoryLimitKb ? null }:
          let
            stages = mkSynthJsonStages {
              inherit name modelIl topName topSv quiet memoryLimitKb;
            };
            utilization = mkMappedJsonUtilizationReport {
              inherit name capacities topName;
              designJson = stages.json;
            };
          in {
            inherit stages utilization;
            json = stages.json;
          };
```

If a flake-false source lacks sourceInfo.rev on the pinned Nix version, obtain the exact revision by reading task3-main/flake.lock with builtins.fromJSON and select nodes.yosys-slang.locked.rev. Do not substitute a moving Git reference or omit the field.

- [ ] **Step 5: Export the API from the per-system result**

Add this sibling of packages in the final in block of task3-main/flake.nix:

```nix
        lib = {
          inherit mkTask3RtlilFromSlangFilelist mkTask3XilinxUtilization
            task3Toolchain;
        };
```

The export must remain inside flake-utils.lib.eachDefaultSystem so the root accesses it as inputs.task3-main-pipeline.lib.${system}.

- [ ] **Step 6: Verify GREEN, format, evaluate, and commit**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
nix fmt task3-main/flake.nix
nix eval ./task3-main#lib.x86_64-linux.task3Toolchain.manifest --raw
nix flake check --no-build
```

Expected: the unit test passes; the manifest evaluates to a Nix store path; and flake evaluation succeeds without building the full design.

Commit only the new test and nested-flake source:

```bash
git add task3-main/flake.nix tests/test_task3_pinned_w8a8_utilization.py
git commit -m "feat: export pinned Task 3 synthesis API"
```

### Task 2: Wire the unchanged W8A8 Calyx main_1 interface to the exported API

**Files:**

- Create: scripts/pipeline/verify_rtlil_top_interface.py
- Modify: tests/test_task3_pinned_w8a8_utilization.py
- Modify: flake.nix:22-24
- Modify: flake.nix:566-573
- Modify: flake.nix package-output block

**Interfaces:**

- Consumes: task3MainLib from Task 1, pipelineAliasPackages."tinystories-w8a8-via-tosa-no-handshake-calyx-native-sv", its sources.f, and task3TinyStoriesCapacities.
- Produces:
  - script interface: verify_rtlil_top_interface.py --rtlil PATH --top NAME --expected-port-count N --expected-port-bits N --required-output NAME --out PATH
  - root derivations:
    - tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-il
    - tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-interface
    - tinystories-w8a8-via-tosa-no-handshake-calyx-task3-expected-interface
    - tinystories-w8a8-via-tosa-no-handshake-calyx-task3-stage1
    - tinystories-w8a8-via-tosa-no-handshake-calyx-task3-stage2
    - tinystories-w8a8-via-tosa-no-handshake-calyx-task3-toolchain-manifest

- [ ] **Step 1: Add failing interface parser and root-route tests**

Append these tests to tests/test_task3_pinned_w8a8_utilization.py. Keep imports json, subprocess, sys, and tempfile with the existing unittest and Path imports.

```python
    def test_rtlil_interface_checker_counts_ports_and_bits(self) -> None:
        script = ROOT / "scripts/pipeline/verify_rtlil_top_interface.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            rtlil = work / "fixture.il"
            output = work / "interface.json"
            rtlil.write_text(
                "\n".join(
                    [
                        "module \\main_1",
                        "  wire width 8 input 1 \\memory_read_data",
                        "  wire width 4 input 2 \\index",
                        "  wire output 3 \\done",
                        "end",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--rtlil",
                    str(rtlil),
                    "--top",
                    "main_1",
                    "--expected-port-count",
                    "3",
                    "--expected-port-bits",
                    "13",
                    "--required-output",
                    "done",
                    "--out",
                    str(output),
                ],
                check=True,
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(report["port_count"], 3)
        self.assertEqual(report["port_bits"], 13)
        self.assertEqual(report["verification"], "verified-after-import")
        self.assertEqual(report["direction_counts"], {"input": 2, "output": 1})
        self.assertEqual(report["required_outputs"], ["done"])

    def test_root_declares_the_direct_main1_task3_route(self) -> None:
        flake = read("flake.nix")

        self.assertIn(
            "task3MainLib = inputs.task3-main-pipeline.lib.${system};", flake
        )
        self.assertIn("task3MainLib.mkTask3RtlilFromSlangFilelist", flake)
        self.assertIn("task3MainLib.mkTask3XilinxUtilization", flake)
        self.assertIn(
            'pipelineAliasPackages."tinystories-w8a8-via-tosa-no-handshake-calyx-native-sv"',
            flake,
        )
        self.assertIn(
            'svFilelist = "${task3W8A8CalyxSv}/sources.f";',
            flake,
        )
        for text in [
            'task3W8A8RouteName = "tinystories-w8a8-via-tosa-no-handshake-calyx-task3";',
            'topName = "main_1";',
            "expected-port-count 12802",
            "expected-port-bits 115933",
            'required-output done',
            '"tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-il"',
            '"tinystories-w8a8-via-tosa-no-handshake-calyx-task3-expected-interface"',
            '"tinystories-w8a8-via-tosa-no-handshake-calyx-task3-stage2"',
            '"tinystories-w8a8-via-tosa-no-handshake-calyx-task3-toolchain-manifest"',
        ]:
            self.assertIn(text, flake)
        self.assertNotIn("task3W8A8Synthesis = mkTask3SynthJsonStages", flake)
        self.assertNotIn("task3W8A8Main1Il = mkTask3YosysRtlil", flake)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
```

Expected: FAIL because the checker and W8A8 Task 3 packages do not exist.

- [ ] **Step 3: Implement the deterministic RTLIL interface checker**

Create scripts/pipeline/verify_rtlil_top_interface.py. It reads only the named RTLIL module, counts each input/output wire once, sums its declared width, verifies named output ports, and emits a small JSON report. It does not alter RTLIL.

```python
#!/usr/bin/env python3
"""Validate and describe a named RTLIL module's top-level port boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtlil", required=True)
    parser.add_argument("--top", required=True)
    parser.add_argument("--expected-port-count", required=True, type=int)
    parser.add_argument("--expected-port-bits", required=True, type=int)
    parser.add_argument("--required-output", action="append", default=[])
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def unescape_rtlil_name(name: str) -> str:
    return name[1:] if name.startswith("\\") else name


def module_port_rows(rtlil: str, top: str) -> list[tuple[str, int, tuple[str, ...]]]:
    target_names = {top, f"\\{top}"}
    in_target = False
    rows: list[tuple[str, int, tuple[str, ...]]] = []
    for raw_line in rtlil.splitlines():
        fields = raw_line.split()
        if not fields:
            continue
        if fields[0] == "module":
            in_target = len(fields) > 1 and fields[1] in target_names
            continue
        if in_target and fields[0] == "end":
            break
        if not in_target or fields[0] != "wire":
            continue
        directions = tuple(
            direction for direction in ("input", "output") if direction in fields
        )
        if not directions:
            continue
        width = 1
        if "width" in fields:
            width = int(fields[fields.index("width") + 1])
        rows.append((unescape_rtlil_name(fields[-1]), width, directions))
    if not rows:
        raise SystemExit(f"no top-level ports found for {top!r}")
    return rows


def main() -> None:
    args = parse_args()
    rows = module_port_rows(Path(args.rtlil).read_text(encoding="utf-8"), args.top)
    port_count = len(rows)
    port_bits = sum(width for _, width, _ in rows)
    output_names = {name for name, _, directions in rows if "output" in directions}
    missing = sorted(set(args.required_output) - output_names)
    if port_count != args.expected_port_count:
        raise SystemExit(
            f"expected {args.expected_port_count} ports, found {port_count}"
        )
    if port_bits != args.expected_port_bits:
        raise SystemExit(
            f"expected {args.expected_port_bits} port bits, found {port_bits}"
        )
    if missing:
        raise SystemExit(f"missing required output ports: {', '.join(missing)}")
    payload = {
        "schema_version": 1,
        "verification": "verified-after-import",
        "top": args.top,
        "port_count": port_count,
        "port_bits": port_bits,
        "direction_counts": {
            direction: sum(direction in directions for _, _, directions in rows)
            for direction in ("input", "output")
        },
        "required_outputs": sorted(args.required_output),
    }
    Path(args.out).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Instantiate direct main_1 import and interface verification in flake.nix**

At the start of the root let block, immediately after task3MainPackages, add:

```nix
        task3MainLib = inputs.task3-main-pipeline.lib.${system};
```

Near task3TinyStoriesCapacities, add the following definitions. The only model input is the generated source list. postReadCommands validates module existence and done without changing logic.

```nix
        task3W8A8RouteName =
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3";
        task3W8A8CalyxSv =
          pipelineAliasPackages."tinystories-w8a8-via-tosa-no-handshake-calyx-native-sv";
        task3W8A8ExpectedInterface = pkgs.writeText
          "${task3W8A8RouteName}-expected-interface.json"
          (builtins.toJSON {
            schema_version = 1;
            verification = "expected-unverified";
            top = "main_1";
            port_count = 12802;
            port_bits = 115933;
            required_outputs = [ "done" ];
          });
        task3W8A8Main1Il = task3MainLib.mkTask3RtlilFromSlangFilelist {
          name = "${task3W8A8RouteName}-main1";
          svFilelist = "${task3W8A8CalyxSv}/sources.f";
          topName = "main_1";
          quiet = true;
          postReadCommands = [
            "select -assert-count 1 main_1"
            "select -assert-count 1 main_1/w:done"
          ];
        };
        task3W8A8Main1Interface = pkgs.runCommand
          "${task3W8A8RouteName}-main1-interface.json" { } ''
            ${python}/bin/python3 ${
              ./scripts/pipeline/verify_rtlil_top_interface.py
            } \
              --rtlil ${task3W8A8Main1Il} \
              --top main_1 \
              --expected-port-count 12802 \
              --expected-port-bits 115933 \
              --required-output done \
              --out "$out"
          '';
        task3W8A8Synthesis = task3MainLib.mkTask3XilinxUtilization {
          name = task3W8A8RouteName;
          modelIl = task3W8A8Main1Il;
          topName = "main_1";
          capacities = task3TinyStoriesCapacities;
          quiet = true;
        };
```

Add these packages in the root packages attrset:

```nix
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-il" =
            task3W8A8Main1Il;
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-interface" =
            task3W8A8Main1Interface;
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-expected-interface" =
            task3W8A8ExpectedInterface;
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-stage1" =
            task3W8A8Synthesis.stages.stage1;
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-stage2" =
            task3W8A8Synthesis.stages.stage2;
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-toolchain-manifest" =
            task3MainLib.task3Toolchain.manifest;
```

Do not instantiate these derivations through mkTask3SynthJsonStages, mkTask3YosysRtlil, or any other root-flake Task 3 helper.

- [ ] **Step 5: Verify GREEN, Nix syntax, and the direct boundary**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
python3 -m py_compile scripts/pipeline/verify_rtlil_top_interface.py
nix fmt flake.nix task3-main/flake.nix
nix eval .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-il.drvPath --raw
nix eval .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-interface.drvPath --raw
```

Expected: tests and Python compilation pass, Nix formats cleanly, and both package derivations evaluate without building the full model.

- [ ] **Step 6: Commit the W8A8 input boundary**

Run:

```bash
git add flake.nix scripts/pipeline/verify_rtlil_top_interface.py \
  tests/test_task3_pinned_w8a8_utilization.py
git commit -m "feat: route W8A8 Calyx SV through Task 3"
```

### Task 3: Package mapped and frontier evidence without changing synthesis

**Files:**

- Create: scripts/pipeline/write_task3_pinned_utilization_result.py
- Modify: tests/test_task3_pinned_w8a8_utilization.py
- Modify: flake.nix package-output block

**Interfaces:**

- Consumes: Task 2 interface JSON, Task 1 toolchain manifest, and on success the Task 3 summary.json.
- Produces:
  - script interface: write_task3_pinned_utilization_result.py --status {mapped,frontier} --stage STAGE --exit-status CODE --toolchain-manifest PATH --interface PATH --command TEXT --out PATH [--utilization-summary PATH] [--monitor-summary PATH]
  - package: tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization.

- [ ] **Step 1: Write failing evidence-writer tests**

Append these tests. Both use the same TemporaryDirectory scope for source files and subprocess invocation, so the child process never observes deleted fixtures.

```python
    def test_evidence_writer_records_a_frontier_without_resources(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            output = work / "result.json"
            toolchain.write_text(
                json.dumps(
                    {
                        "yosys": {"source_rev": "pin"},
                        "yosys_slang": {"source_rev": "slang"},
                    }
                ),
                encoding="utf-8",
            )
            interface.write_text(
                json.dumps(
                    {"top": "main_1", "port_count": 12802, "port_bits": 115933}
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "frontier",
                    "--stage",
                    "stage2",
                    "--exit-status",
                    "137",
                    "--toolchain-manifest",
                    str(toolchain),
                    "--interface",
                    str(interface),
                    "--command",
                    "nix build example",
                    "--out",
                    str(output),
                ],
                check=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "frontier")
        self.assertEqual(result["stage"], "stage2")
        self.assertEqual(result["completed_stages"], ["stage1"])
        self.assertIsNone(result["resources"])
        self.assertFalse(result["downstream"]["technology_mapped_utilization_available"])

    def test_evidence_writer_records_mapped_resources(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            utilization = work / "summary.json"
            output = work / "result.json"
            toolchain.write_text(
                json.dumps({"yosys": {"source_rev": "pin"}}), encoding="utf-8"
            )
            interface.write_text(
                json.dumps(
                    {"top": "main_1", "port_count": 12802, "port_bits": 115933}
                ),
                encoding="utf-8",
            )
            utilization.write_text(
                json.dumps(
                    {
                        "resources": {
                            "clb_luts": {"used": 12, "capacity": 298600}
                        }
                    }
                ),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "mapped",
                    "--stage",
                    "stage9",
                    "--exit-status",
                    "0",
                    "--toolchain-manifest",
                    str(toolchain),
                    "--interface",
                    str(interface),
                    "--utilization-summary",
                    str(utilization),
                    "--command",
                    "nix build example",
                    "--out",
                    str(output),
                ],
                check=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "mapped")
        self.assertEqual(result["completed_stages"][-1], "stage9")
        self.assertEqual(result["resources"]["clb_luts"]["used"], 12)
        self.assertTrue(result["downstream"]["technology_mapped_utilization_available"])
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
```

Expected: FAIL because the evidence writer and final compact package are absent.

- [ ] **Step 3: Implement the evidence writer**

Create scripts/pipeline/write_task3_pinned_utilization_result.py with this implementation. Frontier evidence deliberately has resources null; a mapped result is only legal when it was derived from the existing mapped JSON summary.

```python
#!/usr/bin/env python3
"""Write compact, comparable evidence for the pinned Task 3 W8A8 route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROUTE = (
    "PyTorch PT2E W8A8 -> Torch-MLIR -> TOSA -> Linalg -> SCF -> "
    "Calyx -> native SV -> Task 3 Xilinx synthesis"
)
STAGE_ORDER = [
    "stage1",
    "stage2",
    "stage3",
    "stage4",
    "stage5",
    "stage6",
    "stage7",
    "stage8",
    "stage9",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=["mapped", "frontier"], required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--exit-status", required=True, type=int)
    parser.add_argument("--toolchain-manifest", required=True)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--utilization-summary")
    parser.add_argument("--monitor-summary")
    parser.add_argument("--command", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def load_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def completed_stages(status: str, stage: str) -> list[str]:
    if stage in {"sv-to-rtlil-import", "interface-verify"}:
        return []
    try:
        index = STAGE_ORDER.index(stage)
    except ValueError as error:
        raise SystemExit(f"unrecognized Task 3 stage: {stage}") from error
    if status == "mapped" and stage != "stage9":
        raise SystemExit("mapped status requires stage9")
    end = index + 1 if status == "mapped" else index
    return STAGE_ORDER[:end]


def main() -> None:
    args = parse_args()
    toolchain = load_json(args.toolchain_manifest)
    interface = load_json(args.interface)
    if args.status == "mapped" and not args.utilization_summary:
        raise SystemExit("--utilization-summary is required for mapped status")
    if args.status == "frontier" and args.utilization_summary:
        raise SystemExit("frontier status must not claim a utilization summary")
    summary = load_json(args.utilization_summary) if args.utilization_summary else None
    payload = {
        "schema_version": 1,
        "route": ROUTE,
        "top": interface["top"],
        "status": args.status,
        "stage": args.stage,
        "completed_stages": completed_stages(args.status, args.stage),
        "exit_status": args.exit_status,
        "toolchain": toolchain,
        "external_memory_boundary": {
            "verification": interface.get("verification", "unknown"),
            "port_count": interface["port_count"],
            "port_bits": interface["port_bits"],
            "logical_memories": 2133,
        },
        "resources": None if summary is None else summary["resources"],
        "downstream": {
            "technology_mapped_utilization_available": summary is not None,
            "nextpnr_attempted": False,
            "equivalence_attempted": False,
            "ddr3_controller_present": False,
        },
        "command": args.command,
    }
    if args.monitor_summary:
        payload["monitor_summary"] = Path(args.monitor_summary).read_text(
            encoding="utf-8"
        )
    Path(args.out).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add the compact success bundle**

Near the Task 2 root derivations, create a compact manifest and bundle. It depends on the exact Task 3 final output, but does not copy the huge stage artifacts.

```nix
        task3W8A8Manifest = pkgs.writeText
          "${task3W8A8RouteName}-manifest.json"
          (builtins.toJSON {
            schema_version = 1;
            route =
              "PT2E W8A8 -> TOSA -> no Handshake -> Calyx native SV -> Task 3";
            top = "main_1";
            source_filelist = "${task3W8A8CalyxSv}/sources.f";
            logical_external_memories = 2133;
            expected_port_count = 12802;
            expected_port_bits = 115933;
            stage_order = [
              "stage1"
              "stage2"
              "stage3"
              "stage4"
              "stage5"
              "stage6"
              "stage7"
              "stage8"
              "stage9"
            ];
          });
        task3W8A8UtilizationBundle = pkgs.runCommand
          "${task3W8A8RouteName}-utilization" { } ''
            mkdir -p "$out"
            cp ${task3W8A8Manifest} "$out/manifest.json"
            cp ${task3W8A8Main1Interface} "$out/interface.json"
            cp ${task3MainLib.task3Toolchain.manifest} \
              "$out/task3-yosys-toolchain.json"
            cp ${task3W8A8Synthesis.utilization}/summary.json "$out/summary.json"
            cp ${task3W8A8Synthesis.utilization}/summary.txt "$out/summary.txt"
            cp ${task3W8A8Synthesis.utilization}/stat.json "$out/stat.json"
            ${python}/bin/python3 ${
              ./scripts/pipeline/write_task3_pinned_utilization_result.py
            } \
              --status mapped \
              --stage stage9 \
              --exit-status 0 \
              --toolchain-manifest ${task3MainLib.task3Toolchain.manifest} \
              --interface ${task3W8A8Main1Interface} \
              --utilization-summary ${task3W8A8Synthesis.utilization}/summary.json \
              --command "nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization -L" \
              --out "$out/result.json"
          '';
```

Expose the bundle:

```nix
          "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization" =
            task3W8A8UtilizationBundle;
```

- [ ] **Step 5: Verify GREEN, package evaluation, and commit**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
python3 -m py_compile scripts/pipeline/write_task3_pinned_utilization_result.py
nix fmt flake.nix task3-main/flake.nix
nix eval .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization.drvPath --raw
nix flake check --no-build
```

Expected: both evidence schemas pass unit tests, the final derivation evaluates, and no full-model synthesis has run.

Commit:

```bash
git add flake.nix scripts/pipeline/write_task3_pinned_utilization_result.py \
  tests/test_task3_pinned_w8a8_utilization.py
git commit -m "feat: record pinned Task 3 utilization evidence"
```

### Task 4: Run the exact staged closure and preserve the first real outcome

**Files:**

- Create on successful mapping: artifacts/tinystories-w8a8-calyx-task3-utilization/manifest.json
- Create on successful mapping: artifacts/tinystories-w8a8-calyx-task3-utilization/interface.json
- Create on successful mapping: artifacts/tinystories-w8a8-calyx-task3-utilization/task3-yosys-toolchain.json
- Create on successful mapping: artifacts/tinystories-w8a8-calyx-task3-utilization/summary.json
- Create on successful mapping: artifacts/tinystories-w8a8-calyx-task3-utilization/summary.txt
- Create on successful mapping: artifacts/tinystories-w8a8-calyx-task3-utilization/stat.json
- Create on successful mapping: artifacts/tinystories-w8a8-calyx-task3-utilization/result.json
- Create on a frontier: artifacts/tinystories-w8a8-calyx-task3-utilization/result.json
- Create on a frontier: artifacts/tinystories-w8a8-calyx-task3-utilization/task3-yosys-toolchain.json
- Create on a frontier: artifacts/tinystories-w8a8-calyx-task3-utilization/interface.json

**Interfaces:**

- Consumes: the public packages from Tasks 2 and 3 and scripts/pipeline/monitor_build.sh.
- Produces: either mapped compact XC7K480T evidence or a compact first-frontier record. It never produces a partitioned estimate.

- [ ] **Step 1: Prepare conservative GC roots and monitor directories**

Run:

```bash
mkdir -p /tmp/llm2fpga-gcroots
mkdir -p /tmp/tinystories-w8a8-calyx-task3-monitor
```

Do not run nix-collect-garbage, delete prior checkpoints, or remove any existing Nix store result. The out-link paths below preserve only the exact new checkpoints required for this experiment.

- [ ] **Step 2: Build and validate the cacheable main_1 import**

Run:

```bash
scripts/pipeline/monitor_build.sh \
  /tmp/tinystories-w8a8-calyx-task3-monitor/main1-il 5 -- \
  nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-il \
  --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-main1-il -L

scripts/pipeline/monitor_build.sh \
  /tmp/tinystories-w8a8-calyx-task3-monitor/interface 5 -- \
  nix build \
  .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-main1-interface \
  --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-main1-interface -L

cat /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-main1-interface
```

Expected: the interface JSON reports top main_1, port_count 12802, port_bits 115933, required_outputs containing done, and verification verified-after-import. If import fails, record sv-to-rtlil-import; if the checker fails, record interface-verify. In either case build the expected-interface package, retain its expected-unverified verification field, and do not run a modified source set.

- [ ] **Step 3: Build Stage 1 and record its monitored outcome**

Run:

```bash
MONITOR_GLOBAL_PGREP_PATTERN='yosys.*run.ys' \
scripts/pipeline/monitor_build.sh \
  /tmp/tinystories-w8a8-calyx-task3-monitor/stage1 5 -- \
  nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-stage1 \
  --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-stage1 -L
```

Expected: the exact Task 3 begin:prepare stage completes or produces an explicit first failure with monitored peak memory. Do not manually rerun it with a changed Yosys command.

- [ ] **Step 4: Build Stage 2 and stop at its genuine frontier if it fails**

Run:

```bash
MONITOR_GLOBAL_PGREP_PATTERN='yosys.*run.ys' \
scripts/pipeline/monitor_build.sh \
  /tmp/tinystories-w8a8-calyx-task3-monitor/stage2 5 -- \
  nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-stage2 \
  --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-stage2 -L
```

Expected: Stage 2 runs with the nested Task 3 pinned toolchain. If it fails, inspect its monitor summary and Nix log, then write frontier evidence with the real exit status. Do not invoke submod, change share, or use the root Yosys 0.66 path.

On a failure, inspect the bounded monitoring evidence before writing result.json:

```bash
sed -n '1,160p' /tmp/tinystories-w8a8-calyx-task3-monitor/stage2/summary.txt
rg -n 'mkSynthJson:|Killed|out of memory|cannot allocate|error:' \
  /tmp/tinystories-w8a8-calyx-task3-monitor/stage2/build.log
```

Expected: the monitor summary identifies the command, exit status, peak sampled memory, and last Task 3 stage; the build log supplies the failure signature.

- [ ] **Step 5: If Stage 2 completes, build the final exact utilization package**

Run:

```bash
MONITOR_GLOBAL_PGREP_PATTERN='yosys.*run.ys' \
scripts/pipeline/monitor_build.sh \
  /tmp/tinystories-w8a8-calyx-task3-monitor/final 5 -- \
  nix build .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization \
  --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-utilization -L

readlink -f /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-utilization
```

Expected: a compact output containing summary.json, summary.txt, stat.json, interface.json, task3-yosys-toolchain.json, manifest.json, and result.json. A completed mapped result is the only condition under which LUT, FF, DSP48E1, and BRAM figures may be reported.

- [ ] **Step 6: Capture a compact mapped result or a compact frontier**

For a mapped run, copy only the final bundle:

```bash
mkdir -p artifacts/tinystories-w8a8-calyx-task3-utilization
cp -a /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-utilization/. \
  artifacts/tinystories-w8a8-calyx-task3-utilization/
python3 -m json.tool \
  artifacts/tinystories-w8a8-calyx-task3-utilization/result.json >/dev/null
```

For a failure, select the first failed monitor directory, derive its exit code, and write only bounded frontier evidence:

```bash
monitor_dir=/tmp/tinystories-w8a8-calyx-task3-monitor/stage2
failed_stage=$(sed -n 's/.*\(stage[1-9]\).*/\1/p' "$monitor_dir/summary.txt")
exit_status=$(sed -n 's/^exit_status: //p' "$monitor_dir/summary.txt")
command=$(sed -n 's/^command: //p' "$monitor_dir/summary.txt")
test -n "$failed_stage"
test -n "$exit_status"
test -n "$command"

mkdir -p artifacts/tinystories-w8a8-calyx-task3-utilization
interface_source=/tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-main1-interface
if [ "$failed_stage" = "sv-to-rtlil-import" ] || [ "$failed_stage" = "interface-verify" ]; then
  nix build \
    .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-expected-interface \
    --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-expected-interface -L
  interface_source=/tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-expected-interface
fi
cp "$interface_source" \
  artifacts/tinystories-w8a8-calyx-task3-utilization/interface.json
nix build \
  .#tinystories-w8a8-via-tosa-no-handshake-calyx-task3-toolchain-manifest \
  --out-link /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-toolchain-manifest -L
cp /tmp/llm2fpga-gcroots/tinystories-w8a8-calyx-task3-toolchain-manifest \
  artifacts/tinystories-w8a8-calyx-task3-utilization/task3-yosys-toolchain.json
cp "$monitor_dir/summary.txt" \
  artifacts/tinystories-w8a8-calyx-task3-utilization/monitor-summary.txt
python3 scripts/pipeline/write_task3_pinned_utilization_result.py \
  --status frontier \
  --stage "$failed_stage" \
  --exit-status "$exit_status" \
  --toolchain-manifest \
  artifacts/tinystories-w8a8-calyx-task3-utilization/task3-yosys-toolchain.json \
  --interface artifacts/tinystories-w8a8-calyx-task3-utilization/interface.json \
  --monitor-summary \
  artifacts/tinystories-w8a8-calyx-task3-utilization/monitor-summary.txt \
  --command "$command" \
  --out artifacts/tinystories-w8a8-calyx-task3-utilization/result.json
```

For a Stage 1 failure, set monitor_dir to its matching directory; the command above derives stage1 and the command string. For an import failure, set monitor_dir to the import directory and set failed_stage=sv-to-rtlil-import. For a checker failure, set monitor_dir to the interface directory and set failed_stage=interface-verify. Derive exit_status and command with the same sed expressions. Do not copy RTLIL, full JSON, generated SystemVerilog, or build logs into Git.

- [ ] **Step 7: Validate the observed evidence**

Run:

```bash
python3 -m json.tool \
  artifacts/tinystories-w8a8-calyx-task3-utilization/result.json >/dev/null
rg -n '"status": "(mapped|frontier)"|"port_count": 12802|"port_bits": 115933' \
  artifacts/tinystories-w8a8-calyx-task3-utilization
du -sh artifacts/tinystories-w8a8-calyx-task3-utilization
```

Expected: the evidence is valid JSON, says mapped only if summary resources exist, retains the original external-memory boundary, and is compact.

### Task 5: Document the result, correct the diagnostic boundary, and verify the repository

**Files:**

- Create: docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md
- Modify: docs/current-baseline.md
- Modify: docs/adr/2026-07-13-calyx-memory-blackbox-diagnostic.md
- Modify: tests/test_task3_pinned_w8a8_utilization.py

**Interfaces:**

- Consumes: Task 4 result.json, summary files if mapped, and monitor summary if frontier.
- Produces: an accurate current baseline that distinguishes pre-mapping structural evidence from a real mapped Xilinx estimate.

- [ ] **Step 1: Add a failing documentation regression**

Append this test:

```python
    def test_current_baseline_and_adr_keep_task3_result_scoped(self) -> None:
        baseline = read("docs/current-baseline.md")
        adr = read("docs/adr/2026-07-13-calyx-memory-blackbox-diagnostic.md")

        self.assertIn(
            "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization",
            baseline,
        )
        self.assertIn("XC7K480T", baseline)
        self.assertIn("out-of-context", baseline)
        self.assertIn("Task 3 pinned", adr)
        self.assertIn("not a final mapped utilization result", adr)
        self.assertNotIn("already prove that this", adr)
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
```

Expected: FAIL because the new result has not yet been documented and the old ADR still overstates a partial structural result.

- [ ] **Step 3: Write the bounded result report from observed evidence**

Create docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md with these sections in this order:

1. Method: exact input route, main_1, Task 3 nested toolchain revisions, XC7K480T capacities, and external-memory boundary.
2. Result: quote the status, completed stages, terminal stage, exit status, and exact command from result.json.
3. Resources: if status is mapped, transcribe LUT, FF, DSP48E1, BRAM18, BRAM36-equivalent, and capacity percentages from summary.json. If status is frontier, state that no mapped resource estimate exists and quote the monitor peak/last-stage evidence instead.
4. Interpretation: call it a provisional out-of-context compute/control estimate. State that it is not a DDR3 controller, board implementation, nextpnr result, or numerical-equivalence result.
5. Decision: a mapped result unlocks a later like-for-like comparison with the saved F32 Task 3 report; a frontier ends this plan and leaves any partitioned attempt for a separately approved design.

Do not calculate or claim a W8A8-versus-F32 factor unless both reports have mapped results from comparable methodology.

- [ ] **Step 4: Update baseline and correct the prior ADR**

Add a dated W8A8 Task 3 entry near the top of docs/current-baseline.md. It must name the final package, link to the new result report, state the exact status, and call the estimate out-of-context.

In docs/adr/2026-07-13-calyx-memory-blackbox-diagnostic.md, retain the partial DSP/CARRY4 observations but replace any assertion that they prove the W8A8 kernel does not fit. Use this exact scope sentence:

```markdown
Those pre-mapping counts are a structural diagnostic, not a final mapped utilization result. The Task 3 pinned mapping route is the authoritative utilization experiment for this W8A8 Calyx kernel; until it completes, or records a first mapped-stage frontier, FPGA fit remains unresolved.
```

- [ ] **Step 5: Run final verification**

Run:

```bash
python3 -m unittest tests.test_task3_pinned_w8a8_utilization -v
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/pipeline/verify_rtlil_top_interface.py \
  scripts/pipeline/write_task3_pinned_utilization_result.py
nix flake check --no-build
python3 -m json.tool \
  artifacts/tinystories-w8a8-calyx-task3-utilization/result.json >/dev/null
git diff --check
```

Expected: all Python tests pass, both scripts compile, the flake evaluates, evidence is valid JSON, and the diff has no whitespace errors.

- [ ] **Step 6: Commit only the Task 3 result work**

Run:

```bash
git add docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md \
  docs/current-baseline.md \
  docs/adr/2026-07-13-calyx-memory-blackbox-diagnostic.md \
  artifacts/tinystories-w8a8-calyx-task3-utilization \
  tests/test_task3_pinned_w8a8_utilization.py
git commit -m "docs: record W8A8 Calyx Task 3 utilization"
```

Do not stage the pre-existing docs/glossary.md modification as part of this commit.
