"""Regression evidence for the real package-aware softmax bridge boundary."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/comparison/tinystories-1m-softmax-real-graph-boundary.json"


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


if __name__ == "__main__":
    unittest.main()
