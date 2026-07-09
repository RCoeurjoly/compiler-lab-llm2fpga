import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "pipeline" / "summarize_yosys_stat_baselines.py"


class YosysResourceBaselineMatrixTest(unittest.TestCase):
    def test_summarizes_yosys_stat_reports_with_pipeline_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            stat = tmpdir / "linear.stat.json"
            out_json = tmpdir / "summary.json"
            out_md = tmpdir / "summary.md"

            stat.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "yosys_stat": {
                            "design": {
                                "num_cells": 12,
                                "num_memories": 2,
                                "num_memory_bits": 128,
                                "num_cells_by_type": {
                                    "$and": 5,
                                    "$buf": 7,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--entry",
                    "alias=pattern-linear-w4a8-core-via-tosa-no-handshake,model=pattern-linear-w4a8-core,frontend=tosa,backend=calyx-sv,stat="
                    + str(stat),
                    "--summary-json",
                    str(out_json),
                    "--summary-md",
                    str(out_md),
                ],
                check=True,
            )

            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["schemaVersion"], 1)
            self.assertEqual(payload["entries"][0]["alias"], "pattern-linear-w4a8-core-via-tosa-no-handshake")
            self.assertEqual(payload["entries"][0]["model"], "pattern-linear-w4a8-core")
            self.assertEqual(payload["entries"][0]["frontend"], "tosa")
            self.assertEqual(payload["entries"][0]["backend"], "calyx-sv")
            self.assertEqual(payload["entries"][0]["status"], "ok")
            self.assertEqual(payload["entries"][0]["num_cells"], 12)
            self.assertEqual(payload["entries"][0]["num_memories"], 2)
            self.assertEqual(payload["entries"][0]["num_memory_bits"], 128)
            self.assertEqual(payload["entries"][0]["top_cell_types"][0], {"type": "$buf", "count": 7})

            markdown = out_md.read_text(encoding="utf-8")
            self.assertIn("| alias | frontend | backend | status | cells | memories | memory bits |", markdown)
            self.assertIn("| pattern-linear-w4a8-core-via-tosa-no-handshake | tosa | calyx-sv | ok | 12 | 2 | 128 |", markdown)

    def test_flake_exposes_resource_baseline_matrix_package(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("resourceBaselineYosysStatMatrix", flake)
        self.assertIn('"resource-baseline-yosys-stat-matrix"', flake)
        self.assertIn("summarize_yosys_stat_baselines.py", flake)
        self.assertIn("pattern-linear-w4a8-core-via-tosa-no-handshake-yosys-stat", flake)
        self.assertIn("pattern-embedding-w4a8-core-via-tosa-no-handshake-yosys-stat", flake)
        self.assertIn("pattern-layernorm-w4a8-core-via-tosa-no-handshake-yosys-stat", flake)
        self.assertIn("tinystories-representative-core-w4a8-integer-via-linalg-no-handshake-yosys-stat", flake)


if __name__ == "__main__":
    unittest.main()
