import json
import subprocess
import sys
import tempfile
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

    def test_evidence_writer_rejects_mapped_interface_verify_stage(self) -> None:
        script = ROOT / "scripts/pipeline/write_task3_pinned_utilization_result.py"
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            toolchain = work / "toolchain.json"
            interface = work / "interface.json"
            utilization = work / "summary.json"
            output = work / "result.json"
            toolchain.write_text(json.dumps({}), encoding="utf-8")
            interface.write_text(
                json.dumps({"top": "main_1", "port_count": 1, "port_bits": 1}),
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
            toolchain.write_text(json.dumps({}), encoding="utf-8")
            interface.write_text(
                json.dumps({"top": "main_1", "port_count": 1, "port_bits": 1}),
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
            toolchain.write_text(json.dumps({}), encoding="utf-8")
            interface.write_text(
                json.dumps({"top": "main_1", "port_count": 1, "port_bits": 1}),
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


if __name__ == "__main__":
    unittest.main()
