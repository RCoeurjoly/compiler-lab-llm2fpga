import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "scripts" / "pipeline" / "calyx_float_frontier_report.py"


class CalyxFloatFrontierReportTest(unittest.TestCase):
    def run_report(
        self, mlir: str, *, update_manifest: bool = False
    ) -> tuple[dict[str, object], dict[str, object] | None]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mlir"
            output_path = Path(tmp) / "report.json"
            manifest_path = Path(tmp) / "manifest.json"
            input_path.write_text(mlir, encoding="utf-8")
            cmd = ["python3", str(REPORT), str(input_path), str(output_path)]
            if update_manifest:
                manifest_path.write_text(
                    json.dumps({"stage": "calyx", "status": "failed"}) + "\n",
                    encoding="utf-8",
                )
                cmd.extend(["--manifest-json", str(manifest_path)])
            subprocess.run(cmd, check=True)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if update_manifest
                else None
            )
            return report, manifest

    def test_reports_float_frontier_ops(self) -> None:
        report, _ = self.run_report(
            """
module {
  func.func @main(%arg0: i32) -> i8 {
    %0 = arith.sitofp %arg0 : i32 to f32
    %1 = arith.mulf %0, %0 : f32
    %2 = math.roundeven %1 : f32
    %3 = arith.fptosi %2 : f32 to i8
    return %3 : i8
  }
}
"""
        )

        self.assertEqual(report["status"], "has-float-frontier")
        self.assertEqual(report["total_float_ops"], 4)
        self.assertEqual(report["op_counts"]["arith.sitofp"], 1)
        self.assertEqual(report["op_counts"]["arith.mulf"], 1)
        self.assertEqual(report["op_counts"]["math.roundeven"], 1)
        self.assertEqual(report["op_counts"]["arith.fptosi"], 1)
        self.assertGreaterEqual(report["float_type_lines"], 4)
        self.assertEqual(len(report["samples"]), 4)

    def test_classifies_unsupported_calyx_math_ops(self) -> None:
        report, _ = self.run_report(
            """
module {
  func.func @main(%arg0: f32) -> f32 {
    %0 = math.rsqrt %arg0 : f32
    return %0 : f32
  }
}
"""
        )

        self.assertEqual(report["status"], "has-unsupported-calyx-float-frontier")
        self.assertEqual(report["unsupported_ops"]["math.rsqrt"], 1)
        self.assertEqual(report["unsupported_samples"][0]["ops"], ["math.rsqrt"])
        self.assertIn("math.rsqrt", report["unsupported_samples"][0]["text"])

    def test_classifies_uitofp_as_unsupported_calyx_frontier(self) -> None:
        report, _ = self.run_report(
            """
module {
  func.func @main(%arg0: i1) -> f32 {
    %0 = arith.uitofp %arg0 : i1 to f32
    return %0 : f32
  }
}
"""
        )

        self.assertEqual(report["status"], "has-unsupported-calyx-float-frontier")
        self.assertEqual(report["op_counts"]["arith.uitofp"], 1)
        self.assertEqual(report["unsupported_ops"]["arith.uitofp"], 1)

    def test_can_merge_compact_frontier_summary_into_manifest(self) -> None:
        _, manifest = self.run_report(
            """
module {
  func.func @main(%arg0: f32) -> f32 {
    %0 = math.rsqrt %arg0 : f32
    return %0 : f32
  }
}
""",
            update_manifest=True,
        )

        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["stage"], "calyx")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(
            manifest["float_frontier"]["status"],
            "has-unsupported-calyx-float-frontier",
        )
        self.assertEqual(manifest["float_frontier"]["total_float_ops"], 1)
        self.assertEqual(manifest["float_frontier"]["total_unsupported_ops"], 1)
        self.assertEqual(
            manifest["float_frontier"]["unsupported_ops"], {"math.rsqrt": 1}
        )

    def test_integer_only_ir_is_ok(self) -> None:
        report, _ = self.run_report(
            """
module {
  func.func @main(%arg0: i32) -> i32 {
    %0 = arith.addi %arg0, %arg0 : i32
    return %0 : i32
  }
}
"""
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["total_float_ops"], 0)
        self.assertEqual(report["op_counts"], {})
        self.assertEqual(report["float_type_lines"], 0)
        self.assertEqual(report["unsupported_ops"], {})
        self.assertEqual(report["unsupported_samples"], [])


if __name__ == "__main__":
    unittest.main()
