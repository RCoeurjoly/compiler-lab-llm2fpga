import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_SCRIPT = ROOT / "scripts" / "pipeline" / "write_rc_pnr_evidence.py"


class RcSynthesisBaselineNixTest(unittest.TestCase):
    def test_evidence_parser_records_over_capacity_and_unavailable_timing(self) -> None:
        log_text = """\
Info: Annotating ports with timing budgets for target frequency 12.00 MHz
Info: Device utilisation:
Info:              SLICE_LUTX: 776182/597200   129%
Info:               SLICE_FFX: 35090/597200     5%
Info:                RAMB18E1:     0/ 1910     0%
Info:                RAMB36E1:     0/  955     0%
Info:                 DSP48E1:   245/ 1920    12%
ERROR: Failed to expand region (0, 0) |_> (309, 416) of 776182 SLICE_LUTXs
0 warnings, 1 error
"""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            log = work / "nextpnr.log"
            output = work / "evidence.json"
            log.write_text(log_text, encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(EVIDENCE_SCRIPT),
                    "--log",
                    str(log),
                    "--exit-status",
                    "255",
                    "--out",
                    str(output),
                ],
                check=True,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload["stage"], "placement")
        self.assertEqual(payload["result"], "resource-limit-failure")
        self.assertEqual(payload["resources"]["SLICE_LUTX"]["used"], 776182)
        self.assertEqual(payload["resources"]["SLICE_LUTX"]["available"], 597200)
        self.assertEqual(payload["timing"]["target_mhz"], 12.0)
        self.assertEqual(payload["timing"]["target_period_ns"], 83.333333)
        self.assertEqual(payload["timing"]["status"], "unavailable")
        self.assertEqual(payload["timing"]["critical_paths"], [])
        self.assertIn("legal placement", payload["timing"]["reason"])

    def test_root_flake_exports_four_staged_rc_baseline_artifacts(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertRegex(
            flake,
            r"rcSynthesisBaseline\s*=\s*import\s+\./nix/rc-synthesis-baseline\.nix\s*\{",
        )
        for package in [
            "tinystories-w8a8-rc-xc7k480t-normalized-sv",
            "tinystories-w8a8-rc-xc7k480t-mapped",
            "tinystories-w8a8-rc-xc7k480t-dram-compatible",
            "tinystories-w8a8-rc-xc7k480t-nextpnr-evidence",
        ]:
            self.assertIn(f'"{package}"', flake)

    def test_baseline_derivation_pins_target_and_retains_durable_evidence(self) -> None:
        source = (ROOT / "nix" / "rc-synthesis-baseline.nix").read_text(
            encoding="utf-8"
        )

        for required in [
            "xc7k480tffg1156-1",
            "xc7k480tffg1156.bin",
            "fix_sv_synthesis_frontend.py",
            "--ignore-initial",
            "synth_xilinx -family xc7 -top main",
            "RAM64X1D",
            "RAM128X1D",
            "--freq 12",
            "nextpnr-exit-status.txt",
            "timing-status.json",
            "mapped-stat.json",
            "yosys.log.gz",
            "nextpnr.log.gz",
            "rc-validated-main.sv.gz",
        ]:
            self.assertIn(required, source)
        self.assertRegex(source, r"set \+e[\s\S]*nextpnr-xilinx[\s\S]*nextpnr_status=\$\?")
        self.assertRegex(source, r"test \"\$nextpnr_status\" -ne 0")
        self.assertNotIn("cat > run.ys <<'YOSYS'", source)
        self.assertIn('tee -o "$out/mapped-stat.json" stat -json', source)
        self.assertIn('write_json "$out/mapped.json"', source)

        archive = ROOT / "artifacts" / "rc-validated-main.sv.gz"
        self.assertTrue(archive.is_file())

    def test_task3_toolchain_exposes_pinned_nextpnr_and_chipdb(self) -> None:
        flake = (ROOT / "task3-main" / "flake.nix").read_text(encoding="utf-8")
        toolchain = re.search(
            r"task3Toolchain\s*=\s*\{(?P<body>[\s\S]*?)\n\s*\};\n\n"
            r"\s*mkTask3XilinxUtilization",
            flake,
        )
        self.assertIsNotNone(toolchain)
        body = toolchain.group("body")
        self.assertIn("nextpnr = openXC7Nextpnr;", body)
        self.assertIn("chipdb = fpgaChipdb;", body)
        self.assertIn('part = "xc7k480tffg1156-1";', body)


if __name__ == "__main__":
    unittest.main()
