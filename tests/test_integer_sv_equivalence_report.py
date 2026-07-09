import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "scripts" / "pipeline" / "tinystories_integer_sv_equivalence_report.py"


class IntegerSvEquivalenceReportTest(unittest.TestCase):
    def test_report_marks_current_calyx_sv_as_unobservable_when_only_done_is_output(self) -> None:
        main_sv = textwrap.dedent(
            """
            module main(
              input logic clk,
              input logic reset,
              input logic go,
              output logic done
            );
            endmodule
            """
        )
        expected_json = {
            "input_token_ids": [[3]],
            "pytorch_output_i8": [[[-1, 2]]],
            "pytorch_output_shape": [1, 1, 2],
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sv_dir = tmp_path / "sv"
            sv_dir.mkdir()
            (sv_dir / "main.sv").write_text(main_sv, encoding="utf-8")
            expected_path = tmp_path / "expected.json"
            expected_path.write_text(json.dumps(expected_json), encoding="utf-8")
            out = tmp_path / "report.json"

            subprocess.run(
                [
                    "python3",
                    str(REPORT),
                    "--sv-dir",
                    str(sv_dir),
                    "--expected-json",
                    str(expected_path),
                    "--out",
                    str(out),
                ],
                check=True,
            )

            report = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(report["schemaVersion"], 1)
        self.assertEqual(report["model"], "tinystories-representative-core-w4a8-integer")
        self.assertEqual(report["backend"], "calyx-native-sv")
        self.assertEqual(report["reference"], expected_json)
        self.assertEqual(report["sv"]["top_module"], "main")
        self.assertEqual(report["sv"]["ports"]["outputs"], ["done"])
        self.assertEqual(report["sv"]["observable_functional_outputs"], [])
        self.assertEqual(report["status"], "blocked-unobservable-sv-output")
        self.assertIn("no functional output", report["reason"])


if __name__ == "__main__":
    unittest.main()
