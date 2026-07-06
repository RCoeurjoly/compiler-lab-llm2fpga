import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "diagnostics" / "sv_provenance_report.py"


class SvProvenanceReportTest(unittest.TestCase):
    def test_streams_sv_bundle_and_ranks_normalized_symbol_stems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            main_sv = work / "main.sv"
            helper_sv = work / "helper.sv"
            filelist = work / "sources.f"
            output = work / "report.json"

            main_sv.write_text(
                "\n".join(
                    [
                        "module main(input logic clk);",
                        "  logic [7:0] quantize_per_tensor_42;",
                        "  assign quantize_per_tensor_42 = quantize_per_tensor_43;",
                        "  assign quantize_per_tensor_43 = quantize_per_tensor_44;",
                        "  logic [7:0] layer_norm_9;",
                        "  assign layer_norm_9 = quantize_per_tensor_44;",
                        "endmodule",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            helper_sv.write_text(
                "module helper; assign tiny_1 = tiny_2; endmodule\n",
                encoding="utf-8",
            )
            filelist.write_text(
                f"{main_sv}\n# comment\n\n{helper_sv}\n", encoding="utf-8"
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input-filelist",
                    str(filelist),
                    "--output",
                    str(output),
                    "--top-count",
                    "4",
                ],
                check=True,
            )

            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(report["report_kind"], "sv-provenance-report")
        self.assertEqual(report["bundle"]["file_count"], 2)
        self.assertEqual(report["main_sv"]["lines"], 7)
        self.assertEqual(
            report["top_symbol_stems_by_occurrence"][0]["stem"],
            "quantize_per_tensor",
        )
        self.assertGreaterEqual(
            report["top_symbol_stems_by_occurrence"][0]["count"], 5
        )
        self.assertTrue(
            any(
                "top symbol stems" in line
                for line in report["reviewer_summary_lines"]
            )
        )

    def test_pipeline_exposes_sv_provenance_report_stage(self) -> None:
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn('"sv-provenance-report"', pipeline)
        self.assertIn("mkSvProvenanceReportDerivation", pipeline)
        self.assertIn("svProvenanceReport", pipeline)
        self.assertNotIn("pipelineScripts}/sv_provenance_report.py", pipeline)
        self.assertIn(
            "svProvenanceReport = ./scripts/diagnostics/sv_provenance_report.py",
            flake,
        )
        self.assertIn(
            'alias = "tinystories-representative-core-w4a8-via-tosa-no-handshake"',
            flake,
        )
        self.assertIn('"calyx-sv"', flake)

    def test_filters_generic_ports_and_ranks_assignment_clusters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            main_sv = work / "main.sv"
            filelist = work / "sources.f"
            output = work / "report.json"

            main_sv.write_text(
                "\n".join(
                    [
                        "module main(input logic clock, input logic reset);",
                        "  assign in0_valid = clock;",
                        "  assign out0_ready = reset;",
                        "  assign quantize_per_tensor_42 = quantize_per_tensor_43;",
                        "  assign quantize_per_tensor_43 = quantize_per_tensor_44;",
                        "  assign quantize_per_tensor_44 = quantize_per_tensor_45;",
                        "  assign layer_norm_9 = layer_norm_10;",
                        "endmodule",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            filelist.write_text(f"{main_sv}\n", encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input-filelist",
                    str(filelist),
                    "--output",
                    str(output),
                    "--top-count",
                    "4",
                    "--cluster-lines",
                    "3",
                ],
                check=True,
            )

            report = json.loads(output.read_text(encoding="utf-8"))

        stems = [row["stem"] for row in report["top_symbol_stems_by_occurrence"]]
        self.assertNotIn("clock", stems)
        self.assertNotIn("reset", stems)
        self.assertNotIn("in0_valid", stems)
        self.assertNotIn("out0_ready", stems)
        self.assertEqual(stems[0], "quantize_per_tensor")

        clusters = report["top_main_assignment_clusters_by_lines"]
        self.assertEqual(clusters[0]["dominant_stem"], "quantize_per_tensor")
        self.assertEqual(clusters[0]["assign_lines"], 3)
        self.assertEqual(clusters[0]["line_start"], 4)
        self.assertIn(
            "top main assignment clusters", "\n".join(report["reviewer_summary_lines"])
        )


if __name__ == "__main__":
    unittest.main()
