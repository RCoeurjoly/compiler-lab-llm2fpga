import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "scripts"
    / "pipeline"
    / "summarize_quantized_representative_core_study.py"
)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_full_stage(path: Path) -> None:
    path.mkdir()
    write_json(
        path / "metrics.json",
        {
            "schema_version": 1,
            "lowering_elapsed_ns": 1000,
            "mlir_bytes": 10_000,
            "mlir_sha256": "a" * 64,
        },
    )
    write_json(
        path / "fingerprint.json",
        {
            "schema_version": 1,
            "label": "full",
            "input_sha256": "b" * 64,
            "input_bytes": 10_000,
        },
    )


def write_qualification(
    path: Path,
    label: str,
    eligible: bool,
    speedup: float,
    ir_size_ratio: float = 0.05,
) -> None:
    path.mkdir()
    write_json(
        path / "report.json",
        {
            "schema_version": 1,
            "candidate_label": label,
            "eligible": eligible,
            "coverage": {"complete": eligible},
            "metrics": {
                "lowering_speedup": speedup,
                "torch_mlir_import_speedup": speedup * 2,
                "ir_size_ratio": ir_size_ratio,
            },
            "failure_reasons": [] if eligible else ["missing_operation_signatures"],
        },
    )


class QuantizedRepresentativeCoreStudySummaryTest(unittest.TestCase):
    def test_selects_fastest_eligible_candidate_and_records_negative_candidates(self) -> None:
        self.assertTrue(SCRIPT.exists())
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            full = tmp_path / "full"
            anchor = tmp_path / "anchor"
            wide = tmp_path / "wide"
            invalid = tmp_path / "invalid"
            write_full_stage(full)
            write_qualification(anchor, "anchor", True, 12.0, ir_size_ratio=0.01)
            write_qualification(wide, "wide", True, 101.0, ir_size_ratio=0.05)
            write_qualification(invalid, "invalid", False, 999.0)
            out = tmp_path / "summary.json"
            markdown = tmp_path / "summary.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--full-stage",
                    str(full),
                    "--candidate",
                    f"anchor={anchor}",
                    "--candidate",
                    f"wide={wide}",
                    "--candidate",
                    f"invalid={invalid}",
                    "--out",
                    str(out),
                    "--markdown-out",
                    str(markdown),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["selected_candidate"]["key"], "wide")
            self.assertEqual(payload["structural_finalist"]["key"], "anchor")
            self.assertEqual(
                payload["selected_candidate"]["torch_mlir_import_speedup"],
                202.0,
            )
            self.assertEqual(payload["outcome"], "candidate-selected")
            self.assertEqual(len(payload["candidates"]), 3)
            self.assertIn("Torch-MLIR only", markdown.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
