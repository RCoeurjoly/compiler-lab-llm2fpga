import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "scripts" / "pipeline" / "calyx_preflight_report.py"


class CalyxPreflightReportTest(unittest.TestCase):
    def run_report(
        self, mlir: str, *, require_clean: bool = False
    ) -> tuple[int, dict[str, object] | None, str]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mlir"
            output_path = Path(tmp) / "report.json"
            input_path.write_text(mlir, encoding="utf-8")
            cmd = [sys.executable, str(REPORT), str(input_path), str(output_path)]
            if require_clean:
                cmd.append("--require-clean")
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            report = (
                json.loads(output_path.read_text(encoding="utf-8"))
                if output_path.is_file()
                else None
            )
            return result.returncode, report, result.stderr

    def test_preflight_fails_for_each_prohibited_operation(self) -> None:
        rc, report, stderr = self.run_report(
            "memref.copy %a, %b : memref<1xi8> to memref<1xi8>\n"
            "%0 = arith.uitofp %flag : i1 to f32\n",
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["prohibited_ops"],
            {
                "arith.uitofp": 1,
                "memref.copy": 1,
            },
        )

    def test_preflight_accepts_clean_scalar_mlir(self) -> None:
        rc, report, stderr = self.run_report(
            "%0 = arith.sitofp %arg0 : i32 to f32\n", require_clean=True
        )

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["prohibited_ops"], {})


if __name__ == "__main__":
    unittest.main()
