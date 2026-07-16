import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FINGERPRINT = REPO_ROOT / "scripts" / "pipeline" / "torch_mlir_fingerprint.py"
QUALIFY = (
    REPO_ROOT / "scripts" / "pipeline" / "qualify_quantized_representative_core.py"
)


FULL_MLIR = """
module {
  func.func @main(%arg0: !torch.vtensor<[1,8],si64>) {
    %0 = "torch.foo"(%arg0) : (!torch.vtensor<[1,8],si64>) -> !torch.vtensor<[1,8,64],f32>
    %1 = "torch.bar"(%0) : (!torch.vtensor<[1,8,64],f32>) -> !torch.vtensor<[1,8,64],f32>
    return
  }
}
"""


RC_MLIR = """
module {
  func.func @main(%arg0: !torch.vtensor<[1,8],si64>) {
    %0 = "torch.foo"(%arg0) : (!torch.vtensor<[1,8],si64>) -> !torch.vtensor<[1,8,4],f32>
    %1 = "torch.bar"(%0) : (!torch.vtensor<[1,8,4],f32>) -> !torch.vtensor<[1,8,4],f32>
    return
  }
}
"""


MISSING_EDGE_MLIR = """
module {
  func.func @main(%arg0: !torch.vtensor<[1,8],si64>) {
    %0 = "torch.foo"(%arg0) : (!torch.vtensor<[1,8],si64>) -> !torch.vtensor<[1,8,4],f32>
    %1 = "torch.bar"(%arg0) : (!torch.vtensor<[1,8],si64>) -> !torch.vtensor<[1,8,4],f32>
    return
  }
}
"""


def run_fingerprint(tmp_path: Path, name: str, source: str) -> dict:
    input_path = tmp_path / f"{name}.mlir"
    output_path = tmp_path / f"{name}.json"
    input_path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(FINGERPRINT),
            "--input",
            str(input_path),
            "--label",
            name,
            "--out",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(output_path.read_text(encoding="utf-8"))


def write_metrics(
    path: Path,
    elapsed_ns: int,
    mlir_bytes: int,
    torch_mlir_import_elapsed_ns: int = 0,
) -> None:
    payload = {
        "schema_version": 1,
        "lowering_elapsed_ns": elapsed_ns,
        "mlir_bytes": mlir_bytes,
    }
    if torch_mlir_import_elapsed_ns:
        payload["torch_mlir_import_elapsed_ns"] = torch_mlir_import_elapsed_ns
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


class TorchMlirFingerprintTest(unittest.TestCase):
    def test_fingerprint_derives_normalized_signatures_and_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_fingerprint(Path(tmp), "full", FULL_MLIR)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["operation_names"], ["torch.bar", "torch.foo"])
        self.assertIn(
            "torch.foo :: (!torch.vtensor<[?,?],si64>) -> !torch.vtensor<[?,?,?],f32>",
            payload["operation_signatures"],
        )
        self.assertIn(
            "torch.foo -> torch.bar", payload["producer_consumer_edges"]
        )
        self.assertIn(
            "!torch.vtensor<[?,?,?],f32>", payload["normalized_type_text"]
        )

    def test_qualification_accepts_coverage_and_tenfold_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline = run_fingerprint(tmp_path, "full", FULL_MLIR)
            candidate = run_fingerprint(tmp_path, "rc", RC_MLIR)
            baseline_path = tmp_path / "full.json"
            candidate_path = tmp_path / "rc.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            baseline_metrics = tmp_path / "full-metrics.json"
            candidate_metrics = tmp_path / "rc-metrics.json"
            write_metrics(
                baseline_metrics,
                elapsed_ns=1_000,
                mlir_bytes=10_000,
                torch_mlir_import_elapsed_ns=800,
            )
            write_metrics(
                candidate_metrics,
                elapsed_ns=100,
                mlir_bytes=1_000,
                torch_mlir_import_elapsed_ns=40,
            )
            report_path = tmp_path / "report.json"
            markdown_path = tmp_path / "report.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(QUALIFY),
                    "--baseline",
                    str(baseline_path),
                    "--candidate",
                    str(candidate_path),
                    "--baseline-metrics",
                    str(baseline_metrics),
                    "--candidate-metrics",
                    str(candidate_metrics),
                    "--out",
                    str(report_path),
                    "--markdown-out",
                    str(markdown_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["eligible"])
            self.assertEqual(report["failure_reasons"], [])
            self.assertEqual(report["metrics"]["torch_mlir_import_speedup"], 20.0)
            self.assertIn("Torch-MLIR only", markdown_path.read_text(encoding="utf-8"))

    def test_qualification_rejects_missing_edge_even_when_ops_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline = run_fingerprint(tmp_path, "full", FULL_MLIR)
            candidate = run_fingerprint(tmp_path, "rc", MISSING_EDGE_MLIR)
            baseline_path = tmp_path / "full.json"
            candidate_path = tmp_path / "rc.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            baseline_metrics = tmp_path / "full-metrics.json"
            candidate_metrics = tmp_path / "rc-metrics.json"
            write_metrics(baseline_metrics, elapsed_ns=1_000, mlir_bytes=10_000)
            write_metrics(candidate_metrics, elapsed_ns=10, mlir_bytes=10)
            report_path = tmp_path / "report.json"
            markdown_path = tmp_path / "report.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(QUALIFY),
                    "--baseline",
                    str(baseline_path),
                    "--candidate",
                    str(candidate_path),
                    "--baseline-metrics",
                    str(baseline_metrics),
                    "--candidate-metrics",
                    str(candidate_metrics),
                    "--out",
                    str(report_path),
                    "--markdown-out",
                    str(markdown_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["eligible"])
            self.assertIn("missing_producer_consumer_edges", report["failure_reasons"])


if __name__ == "__main__":
    unittest.main()
