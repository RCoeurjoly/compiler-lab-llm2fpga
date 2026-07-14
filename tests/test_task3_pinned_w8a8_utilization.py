import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YOSYS_REV = "4716f4410f1508cad384d2f8542ada9f61bb7339"
YOSYS_SLANG_REV = "d82b0b163a725fc1a401fbb6b465cd862517ec1f"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def normalize_whitespace(prose: str) -> str:
    return " ".join(prose.split())


def select_level_two_section(document: str, heading: str) -> str:
    start = document.index(f"## {heading}")
    end = document.find("\n## ", start + 1)
    return document[start:] if end == -1 else document[start:end]


def select_paragraph_starting_with(document: str, opening: str) -> str:
    start = document.index(opening)
    end = document.find("\n\n", start)
    return document[start:] if end == -1 else document[start:end]


def valid_toolchain_manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": "task3-main",
        "yosys": {"package_version": "unstable-4716f441", "source_rev": YOSYS_REV},
        "yosys_slang": {
            "package_version": "flake-input",
            "source_rev": YOSYS_SLANG_REV,
        },
    }


def valid_interface_manifest(verification: str) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "top": "main_1",
        "port_count": 12802,
        "port_bits": 115933,
        "required_outputs": ["done"],
        "verification": verification,
    }
    if verification == "verified-after-import":
        manifest["direction_counts"] = {"input": 12801, "output": 1}
    return manifest


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

        self.assertIn(
            "read_slang --threads 1 --no-proc --max-parse-depth 20000", flake
        )
        self.assertIn("mkSynthJsonStages", flake)
        self.assertIn("stages = mkSynthJsonStages {", flake)
        self.assertIn("mkMappedJsonUtilizationReport", flake)

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

    def test_evidence_writer_records_a_frontier_without_resources(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("verified-after-import")),
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

    def test_evidence_writer_records_native_sv_generation_frontier(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("expected-unverified")),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "frontier",
                    "--stage",
                    "native-sv-generation",
                    "--exit-status",
                    "1",
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

        self.assertEqual(result["stage"], "native-sv-generation")
        self.assertEqual(result["completed_stages"], [])

    def test_evidence_writer_records_mapped_resources(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            utilization = work / "summary.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("verified-after-import")),
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

    def test_evidence_writer_rejects_mapped_result_with_unverified_interface(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            utilization = work / "summary.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("expected-unverified")),
                encoding="utf-8",
            )
            utilization.write_text(json.dumps({"resources": {}}), encoding="utf-8")

            result = subprocess.run(
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
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("verified-after-import", result.stderr)

    def test_evidence_writer_rejects_empty_toolchain_manifest(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps({}), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("expected-unverified")),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "frontier",
                    "--stage",
                    "native-sv-generation",
                    "--exit-status",
                    "1",
                    "--toolchain-manifest",
                    str(toolchain),
                    "--interface",
                    str(interface),
                    "--command",
                    "nix build example",
                    "--out",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("toolchain manifest", result.stderr)

    def test_evidence_writer_rejects_wrong_yosys_pin(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            output = work / "result.json"
            wrong_toolchain = valid_toolchain_manifest()
            wrong_toolchain["yosys"] = {
                "package_version": "unstable-incorrect",
                "source_rev": "not-the-task3-pin",
            }
            toolchain.write_text(json.dumps(wrong_toolchain), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("expected-unverified")),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "frontier",
                    "--stage",
                    "native-sv-generation",
                    "--exit-status",
                    "1",
                    "--toolchain-manifest",
                    str(toolchain),
                    "--interface",
                    str(interface),
                    "--command",
                    "nix build example",
                    "--out",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Yosys source revision", result.stderr)

    def test_evidence_writer_rejects_unverified_task3_stage_frontier(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("expected-unverified")),
                encoding="utf-8",
            )

            result = subprocess.run(
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
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("verified-after-import", result.stderr)

    def test_evidence_writer_rejects_mapped_interface_verify_stage(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            utilization = work / "summary.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("verified-after-import")),
                encoding="utf-8",
            )
            utilization.write_text(json.dumps({"resources": {}}), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "mapped",
                    "--stage",
                    "interface-verify",
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
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)

    def test_evidence_writer_rejects_mapped_nonzero_exit_status(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            utilization = work / "summary.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("verified-after-import")),
                encoding="utf-8",
            )
            utilization.write_text(json.dumps({"resources": {}}), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "mapped",
                    "--stage",
                    "stage9",
                    "--exit-status",
                    "137",
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
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)

    def test_evidence_writer_rejects_frontier_zero_exit_status(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps(valid_toolchain_manifest()), encoding="utf-8")
            interface.write_text(
                json.dumps(valid_interface_manifest("verified-after-import")),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--status",
                    "frontier",
                    "--stage",
                    "stage2",
                    "--exit-status",
                    "0",
                    "--toolchain-manifest",
                    str(toolchain),
                    "--interface",
                    str(interface),
                    "--command",
                    "nix build example",
                    "--out",
                    str(output),
                ],
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)

    def test_committed_toolchain_manifest_matches_task3_lock_pins(self) -> None:
        manifest = json.loads(
            read(
                "artifacts/tinystories-w8a8-calyx-task3-utilization/"
                "task3-yosys-toolchain.json"
            )
        )
        result = json.loads(
            read("artifacts/tinystories-w8a8-calyx-task3-utilization/result.json")
        )
        lock = json.loads(read("task3-main/flake.lock"))

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["source"], "task3-main")
        self.assertEqual(
            manifest["yosys"]["source_rev"],
            lock["nodes"]["yosys"]["locked"]["rev"],
        )
        self.assertEqual(
            manifest["yosys_slang"]["source_rev"],
            lock["nodes"]["yosys-slang"]["locked"]["rev"],
        )
        self.assertEqual(result["toolchain"], manifest)

    def test_current_baseline_and_adr_keep_task3_result_scoped(self) -> None:
        result = json.loads(
            read("artifacts/tinystories-w8a8-calyx-task3-utilization/result.json")
        )
        report = read(
            "docs/results/2026-07-14-tinystories-w8a8-calyx-task3-utilization.md"
        )
        baseline = read("docs/current-baseline.md")
        adr = read("docs/adr/2026-07-13-calyx-memory-blackbox-diagnostic.md")

        self.assertEqual(result["status"], "frontier")
        self.assertEqual(result["stage"], "native-sv-generation")
        self.assertEqual(result["completed_stages"], [])
        self.assertEqual(result["exit_status"], 1)
        self.assertIsNone(result["resources"])

        self.assertIn('status: "frontier"', report)
        self.assertIn("completed_stages: []", report)
        self.assertIn('"native-sv-generation"', report)
        self.assertIn("exit_status: 1", report)
        self.assertIn("resources: null", report)
        self.assertIn("No mapped resource estimate exists", report)
        self.assertIn(
            "tinystories-w8a8-via-tosa-no-handshake-calyx-task3-utilization",
            baseline,
        )
        self.assertIn("XC7K480T", baseline)
        self.assertIn("native-sv-generation", baseline)
        self.assertIn("no mapped resource estimate", baseline)
        self.assertIn(
            "Compact evidence: `completed_stages: []`; `resources: null`; "
            "FPGA fit remains unresolved.",
            baseline,
        )
        self.assertIn("Task 3 pinned", adr)
        self.assertIn("not a final mapped utilization result", adr)
        self.assertIn("native-SV generation", adr)
        self.assertIn("FPGA fit remains unresolved", adr)

        baseline_scope = select_level_two_section(
            baseline,
            "Full TinyStories PT2E W8A8, Task 3 pinned Calyx utilization frontier",
        )
        adr_scope = select_paragraph_starting_with(
            adr,
            "Those pre-mapping counts are a structural diagnostic",
        )
        structural_fit_claim = (
            r"(?i)\b(?:structural|pre-mapping)\b[^.]*"
            r"\b(?:proves?|confirms?)\b[^.]*"
            r"\b(?:does\s+not\s+|non-?)?fit\b"
        )
        self.assertRegex(
            normalize_whitespace(
                "Structural evidence\nconfirms the kernel does not fit"
            ),
            structural_fit_claim,
        )
        fixture = (
            "## Historical W8A8 run\n\n"
            "Structural evidence confirms the kernel does not fit.\n\n"
            "## Full TinyStories PT2E W8A8, Task 3 pinned Calyx utilization frontier\n\n"
            "FPGA fit remains unresolved.\n\n"
            "## Later material\n\n"
            "Unrelated historical context.\n"
        )
        self.assertRegex(normalize_whitespace(fixture), structural_fit_claim)
        self.assertNotRegex(
            normalize_whitespace(
                select_level_two_section(
                    fixture,
                    "Full TinyStories PT2E W8A8, Task 3 pinned Calyx utilization frontier",
                )
            ),
            structural_fit_claim,
        )
        for path, prose in {
            "result report": report,
            "current baseline W8A8 section": baseline_scope,
            "ADR Task 3 scope paragraph": adr_scope,
        }.items():
            self.assertNotRegex(
                normalize_whitespace(prose), structural_fit_claim, path
            )


if __name__ == "__main__":
    unittest.main()
