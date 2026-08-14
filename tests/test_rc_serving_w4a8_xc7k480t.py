import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "write_w4a8_xc7_evidence.py"
MODULE = ROOT / "nix" / "rc-serving-w4a8-xc7k480t.nix"
KEY = "tinystories-w4a8-rc-serving-mask10-vocab6-width2"
DEFAULT_TIME = object()
GNU_TIME_FIXTURE = """\
\tUser time (seconds): 1.25
\tSystem time (seconds): 0.50
\tElapsed (wall clock) time (h:mm:ss or m:ss): 0:02.00
\tMaximum resident set size (kbytes): 123456
"""


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def run_parser(work: Path, *, yosys_status: str, nextpnr_status: str,
               yosys_stat: str | None = None, nextpnr_log: str = "",
               fasm: str | None = None, yosys_time: object = DEFAULT_TIME,
               nextpnr_time: object = DEFAULT_TIME) -> dict[str, object]:
    source = write(work / "source.sv", "module main; endmodule\n")
    normalized = write(work / "normalized.sv", "module main; endmodule\n")
    receipt = write(work / "normalization-receipt.json", '{"status":"ok"}\n')
    yosys_status_path = write(work / "yosys-status.txt", yosys_status + "\n")
    nextpnr_status_path = write(work / "nextpnr-status.txt", nextpnr_status + "\n")
    yosys_log = write(work / "yosys.log", "Yosys fixture\n")
    nextpnr_log_path = write(work / "nextpnr.log", nextpnr_log)
    yosys_time_path = work / "yosys.time"
    nextpnr_time_path = work / "nextpnr.time"
    if yosys_time is not DEFAULT_TIME and yosys_time is not None:
        write(yosys_time_path, yosys_time)
    elif yosys_time is DEFAULT_TIME and yosys_status == "0":
        write(yosys_time_path, GNU_TIME_FIXTURE)
    if nextpnr_time is not DEFAULT_TIME and nextpnr_time is not None:
        write(nextpnr_time_path, nextpnr_time)
    elif nextpnr_time is DEFAULT_TIME and nextpnr_status == "0":
        write(nextpnr_time_path, GNU_TIME_FIXTURE)
    output = work / "result.json"
    command = [
        sys.executable, str(SCRIPT), "--phase", "prefill-8",
        "--source", str(source), "--normalized", str(normalized),
        "--normalization-receipt", str(receipt),
        "--yosys-status", str(yosys_status_path), "--yosys-log", str(yosys_log),
        "--yosys-time", str(yosys_time_path), "--nextpnr-status", str(nextpnr_status_path),
        "--nextpnr-log", str(nextpnr_log_path), "--nextpnr-time", str(nextpnr_time_path),
        "--out", str(output),
    ]
    if yosys_stat is not None:
        command += ["--yosys-stat", str(write(work / "mapped-stat.json", yosys_stat))]
    if fasm is not None:
        command += ["--fasm", str(write(work / "design.fasm", fasm))]
    subprocess.run(command, check=True)
    return json.loads(output.read_text(encoding="utf-8"))


class RcServingW4A8Xc7k480tTest(unittest.TestCase):
    def test_parser_records_mapped_evidence_but_not_a_fit_without_pnr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_parser(
                Path(tmp),
                yosys_status="0",
                nextpnr_status="not-run: Yosys mapped JSON was unavailable",
                yosys_stat=json.dumps({"modules": {"main": {"num_cells_by_type": {
                    "LUT6": 12, "FDRE": 7, "DSP48E1": 2, "RAMB36E1": 1
                }}}}),
            )

        self.assertEqual(payload["schema"], "llm2fpga.w4a8-xc7k480t-evidence.v1")
        self.assertEqual(payload["fit"], "undetermined")
        self.assertEqual(payload["failure"]["stage"], "nextpnr")
        self.assertEqual(payload["resources"]["mapped"], {
            "bram18": 0, "bram36": 1, "clb_ffs": 7, "clb_luts": 12, "dsp": 2,
        })
        self.assertEqual(payload["tools"]["yosys"]["time"], {
            "status": "available",
            "elapsed_seconds": 2.0,
            "user_cpu_seconds": 1.25,
            "system_cpu_seconds": 0.5,
            "peak_rss_kbytes": 123456,
        })
        self.assertEqual(payload["tools"]["nextpnr"]["time"]["status"], "unavailable")
        self.assertEqual(payload["provenance"]["phase"], "prefill-8")
        self.assertEqual(len(payload["provenance"]["source_sha256"]), 64)
        self.assertEqual(len(payload["provenance"]["normalized_sha256"]), 64)

    def test_parser_preserves_yosys_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_parser(
                Path(tmp), yosys_status="1", nextpnr_status="not-run: Yosys exited 1"
            )

        self.assertEqual(payload["fit"], "undetermined")
        self.assertEqual(payload["failure"], {
            "stage": "yosys", "diagnostic": "Yosys fixture",
        })
        self.assertEqual(payload["tools"]["nextpnr"]["status"], "not-run")
        self.assertEqual(payload["tools"]["yosys"]["time"]["status"], "unavailable")
        self.assertEqual(payload["tools"]["nextpnr"]["time"]["status"], "unavailable")

    def test_parser_rejects_malformed_and_absent_time_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_parser(
                Path(tmp),
                yosys_status="1",
                nextpnr_status="0",
                yosys_time="not a GNU time receipt\n",
                nextpnr_time=None,
                fasm="# FASM\n",
            )

        self.assertEqual(payload["tools"]["yosys"]["time"]["status"], "unavailable")
        self.assertEqual(payload["tools"]["nextpnr"]["time"]["status"], "unavailable")

    def test_parser_retains_indented_gnu_time_for_a_failed_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_parser(
                Path(tmp),
                yosys_status="1",
                nextpnr_status="not-run: Yosys exited 1",
                yosys_time=GNU_TIME_FIXTURE,
            )

        self.assertEqual(payload["tools"]["yosys"]["time"], {
            "status": "available",
            "elapsed_seconds": 2.0,
            "user_cpu_seconds": 1.25,
            "system_cpu_seconds": 0.5,
            "peak_rss_kbytes": 123456,
        })

    def test_parser_uses_escaped_yosys_main_without_counting_submodules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_parser(
                Path(tmp),
                yosys_status="0",
                nextpnr_status="not-run: Yosys mapped JSON was unavailable",
                yosys_stat=json.dumps({"modules": {
                    "\\main": {"num_cells_by_type": {"LUT6": 12, "FDRE": 7}},
                    "submodule": {"num_cells_by_type": {"LUT6": 99, "FDRE": 88}},
                }}),
            )

        self.assertEqual(payload["resources"]["mapped"], {
            "bram18": 0, "bram36": 0, "clb_ffs": 7, "clb_luts": 12, "dsp": 0,
        })

    def test_parser_records_successful_nextpnr_as_fit_with_timing(self) -> None:
        log = """\
Info: Annotating ports with timing budgets for target frequency 12.00 MHz
Info: Device utilisation:
Info:              SLICE_LUTX: 12/597200 0%
Info:               SLICE_FFX: 7/597200 0%
Info:                 DSP48E1: 2/1920 0%
Info: Max frequency for clock 'clk': 34.50 MHz
"""
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_parser(
                Path(tmp), yosys_status="0", nextpnr_status="0", nextpnr_log=log,
                fasm="# FASM\n",
            )

        self.assertEqual(payload["fit"], "fits")
        self.assertEqual(payload["failure"], None)
        self.assertEqual(payload["timing"]["status"], "available")
        self.assertEqual(payload["resources"]["placed"]["clb_luts"]["used"], 12)
        self.assertEqual(payload["resources"]["placed"]["dsp"]["available"], 1920)

    def test_parser_records_over_capacity_nextpnr_failure_as_does_not_fit(self) -> None:
        log = """\
Info: Device utilisation:
Info:              SLICE_LUTX: 776182/597200 129%
ERROR: Failed to expand region (0, 0) |_> (309, 416) of 776182 SLICE_LUTXs
"""
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_parser(
                Path(tmp), yosys_status="0", nextpnr_status="255", nextpnr_log=log
            )

        self.assertEqual(payload["fit"], "does-not-fit")
        self.assertEqual(payload["failure"]["stage"], "nextpnr")
        self.assertIn("Failed to expand region", payload["failure"]["diagnostic"])
        self.assertEqual(payload["timing"]["status"], "unavailable")

    def test_nix_module_keeps_all_tool_outcomes_and_uses_xc7k480t_inputs(self) -> None:
        source = MODULE.read_text(encoding="utf-8")
        self.assertRegex(source, r'targetPart = "xc7k480tffg1156-1";')
        self.assertRegex(source, r'targetChipdb = "xc7k480tffg1156\.bin";')
        for required in (
            "xc7k480tffg1156-1", "xc7k480tffg1156.bin",
            "RAM64X1S", "RAM128X1S", "RAM64X1D", "RAM128X1D", "mapped.json",
            "mapped-stat.json", "normalization-receipt.json", "result.json", "sha256sums.txt",
            "yosys-status.txt", "yosys.log", "yosys.time", "nextpnr-status.txt",
            "nextpnr.log", "nextpnr.time", "nextpnr-xilinx", "--chipdb", "--log",
            "set +e", "${pkgs.time}/bin/time -v", "not-run",
        ):
            self.assertIn(required, source)
        self.assertRegex(source, r"nextpnr_status=\$\?")
        self.assertRegex(source, r"if \[ -s \"\$out/mapped\.json\" \]; then")
        self.assertRegex(source, r"nextpnr-xilinx\s+--chipdb\s+\$\{chipdb\}")

    def test_flake_exports_each_phase_evidence_package_from_its_native_sv_closure(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn("rcServingW4A8Xc7Evidence", flake)
        self.assertIn("fix_sv_synthesis_frontend.py", flake)
        self.assertIn("write_w4a8_xc7_evidence.py", flake)
        for phase in ("prefill-8", "decode-8", "decode-9"):
            package = f"{KEY}-{phase}-xc7k480t-evidence"
            native_sv = f'{KEY}-{phase}-calyx-native-sv'
            match = re.search(
                rf'"{re.escape(package)}"\s*=\s*'
                r'import ./nix/rc-serving-w4a8-xc7k480t\.nix \{(?P<body>.*?)\n\s*\};',
                flake,
                re.DOTALL,
            )
            self.assertIsNotNone(match)
            body = match.group("body")
            self.assertIn(f'phaseName = "{phase}";', body)
            self.assertIn(
                f'rcServingW4A8PipelinePackages."{native_sv}"', body
            )
            self.assertIn("chipdb = task3MainLib.task3Toolchain.chipdb;", body)
            self.assertIn("nextpnr = task3MainLib.task3Toolchain.nextpnr;", body)


if __name__ == "__main__":
    unittest.main()
