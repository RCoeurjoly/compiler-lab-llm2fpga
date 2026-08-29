"""Regression evidence for the real package-aware softmax bridge boundary."""

from __future__ import annotations

import json
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/comparison/tinystories-1m-softmax-real-graph-boundary.json"
FRONTIER = ROOT / "artifacts/comparison/tinystories-1m-package-aware-lowering-frontier.json"
BRIDGE = ROOT / "scripts/comparison/bridge_tinystories_1m_softmax.py"
VERIFY = ROOT / "scripts/comparison/verify_tinystories_1m_softmax_real_graph_boundary.py"
spec = importlib.util.spec_from_file_location("real_graph_boundary", VERIFY)
assert spec and spec.loader
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class RealGraphSoftmaxBoundaryTest(unittest.TestCase):
    def test_real_graph_attempt_is_fail_closed_and_authenticated(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["schema"], "tinystories-1m-softmax-real-graph-bridge-boundary-v1")
        self.assertEqual(report["bridge_revision"], "861862d")
        self.assertEqual(report["status"], "unsupported")
        attempt = report["attempt"]
        self.assertEqual(attempt["expected_exp_sites"], 8)
        self.assertEqual(attempt["observed_exp_sites"], 8)
        mismatch = attempt["first_mismatch"]
        self.assertEqual(mismatch["code"], "dataflow_not_proven")
        self.assertEqual(mismatch["site"], 1)
        self.assertEqual(mismatch["message"], "site 1 lhs is not score")
        self.assertFalse(report["claims"]["authenticated_bridge_emitted"])
        self.assertFalse(report["claims"]["hardware_inference"])

    def test_report_tamper_is_rejected_before_stage_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory) / "report.json"
            value = json.loads(REPORT.read_text(encoding="utf-8"))
            value["attempt"]["observed_exp_sites"] = 7
            tampered.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(verifier.BoundaryVerificationError, "boundary_report_self_hash_mismatch"):
                verifier.verify(tampered, FRONTIER, BRIDGE, {})

    def test_stage_tamper_is_rejected_even_when_pattern_still_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            flat = Path(directory) / "flat.scf.mlir"
            original = Path("/tmp/task3ad-pipeline/flat/flat.scf.mlir")
            if not original.is_file():
                self.skipTest("real package-aware stage materialization is not present")
            flat.write_bytes(original.read_bytes() + b"\n")
            paths = {
                "torch_mlir": Path("/tmp/task3ad-mlir/model.torch.mlir"),
                "linalg": Path("/tmp/task3ad-pipeline/model.linalg.mlir"),
                "scf": Path("/tmp/task3ad-pipeline/model.scf.mlir"),
                "flat_scf": flat,
            }
            if not all(path.is_file() for path in paths.values()):
                self.skipTest("real package-aware stage materialization is not present")
            with self.assertRaisesRegex(verifier.BoundaryVerificationError, "stage_identity_mismatch:flat_scf"):
                verifier.verify(REPORT, FRONTIER, BRIDGE, paths)


if __name__ == "__main__":
    unittest.main()
