import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "task3-main" / "scripts" / "pipeline" / "write_nextpnr_xilinx_report.py"


class DirectLinalgXc7k480tUtilizationTest(unittest.TestCase):
    def test_route_status_requires_successful_exit_and_nonempty_fasm(self) -> None:
        cases = [
            (
                None,
                "missing",
                "incomplete",
                "nextpnr exited with status 0 but did not produce a nonempty FASM",
                0,
            ),
            (
                "",
                "empty",
                "incomplete",
                "nextpnr exited with status 0 but did not produce a nonempty FASM",
                0,
            ),
            (
                "# FASM\n",
                "present",
                "success",
                "nextpnr exited with status 0 and produced a nonempty FASM",
                0,
            ),
            (
                "# FASM\n",
                "present",
                "failed",
                "nextpnr exited with status 1",
                1,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            log = work / "nextpnr.log"
            stdout = work / "stdout.log"
            stderr = work / "stderr.log"
            log.write_text("Info: Device utilisation:\n", encoding="utf-8")
            stdout.write_text("route stdout\n", encoding="utf-8")
            stderr.write_text("", encoding="utf-8")

            for (
                contents,
                expected_fasm_status,
                expected_route_status,
                expected_reason,
                exit_status,
            ) in cases:
                with self.subTest(fasm=expected_fasm_status):
                    fasm = work / "design.fasm"
                    report = work / "route.json"
                    if contents is None:
                        fasm.unlink(missing_ok=True)
                    else:
                        fasm.write_text(contents, encoding="utf-8")

                    subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--nextpnr-log",
                            str(log),
                            "--stdout-log",
                            str(stdout),
                            "--stderr-log",
                            str(stderr),
                            "--exit-status",
                            str(exit_status),
                            "--fasm",
                            str(fasm),
                            "--out",
                            str(report),
                        ],
                        check=True,
                    )
                    payload = json.loads(report.read_text(encoding="utf-8"))

                    self.assertEqual(payload["route"]["exit_status"], exit_status)
                    self.assertEqual(payload["route"]["status"], expected_route_status)
                    self.assertEqual(payload["fasm"]["status"], expected_fasm_status)
                    self.assertEqual(payload["route"]["reason"], expected_reason)

    def test_parser_records_route_frontier_and_arbitrary_device_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            log = work / "nextpnr.log"
            stdout = work / "stdout.log"
            stderr = work / "stderr.log"
            fasm = work / "design.fasm"
            report = work / "route.json"
            log.write_text(
                "\n".join(
                    [
                        "Info: Device utilisation:",
                        "Info:             SLICE_LUT: 123/298600 0%",
                        "Info: custom-routing-widget: 4 / 7 57%",
                        "Info:           MYSTERY-THING: 0/2 0%",
                        "Info: Placing design.",
                        "Info: must-not-be-parsed: 9 / 10 90%",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            stdout.write_text("route stdout\n", encoding="utf-8")
            stderr.write_text("route failed\n", encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--nextpnr-log",
                    str(log),
                    "--stdout-log",
                    str(stdout),
                    "--stderr-log",
                    str(stderr),
                    "--exit-status",
                    "1",
                    "--fasm",
                    str(fasm),
                    "--out",
                    str(report),
                ],
                check=True,
            )
            payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["report_kind"], "nextpnr-xilinx-pnr-report")
        self.assertEqual(payload["route"]["exit_status"], 1)
        self.assertEqual(payload["route"]["status"], "failed")
        self.assertEqual(
            payload["device_utilisation"],
            [
                {"name": "SLICE_LUT", "used": 123, "available": 298600, "pct": 0},
                {
                    "name": "custom-routing-widget",
                    "used": 4,
                    "available": 7,
                    "pct": 57,
                },
                {"name": "MYSTERY-THING", "used": 0, "available": 2, "pct": 0},
            ],
        )
        self.assertEqual(payload["route"]["reason"], "nextpnr exited with status 1")
        self.assertEqual(payload["fasm"]["status"], "missing")

    def test_nested_flake_exports_report_helper_with_pinned_pnr_inputs(self) -> None:
        flake = (ROOT / "task3-main" / "flake.nix").read_text(encoding="utf-8")

        lib_exports = re.search(
            r"\blib\s*=\s*\{\s*inherit\s+(?P<names>[^;]+);",
            flake,
            re.DOTALL,
        )
        self.assertIsNotNone(lib_exports)
        self.assertIn(
            "mkTask3XilinxPnrReport", lib_exports.group("names").split()
        )
        for option in ["--chipdb", "--xdc", "--json", "--fasm", "--log"]:
            self.assertIn(option, flake)
        self.assertIn("write_nextpnr_xilinx_report.py", flake)
        self.assertIn("set +e", flake)
        self.assertRegex(
            flake,
            r'nextpnr-xilinx[\s\S]*?>"\$out/stdout\.log" '
            r'2>"\$out/stderr\.log"\s*'
            r'route_exit_status=\$\?',
        )
        for artifact in [
            '"$out/nextpnr.log"',
            '"$out/stdout.log"',
            '"$out/stderr.log"',
            '"$out/design.fasm"',
            '"$out/route.json"',
        ]:
            self.assertIn(artifact, flake)
        self.assertRegex(
            flake,
            r'write_nextpnr_xilinx_report\.py[\s\S]*?'
            r'--exit-status "\$route_exit_status"[\s\S]*?'
            r'--out "\$out/route\.json"',
        )


if __name__ == "__main__":
    unittest.main()
