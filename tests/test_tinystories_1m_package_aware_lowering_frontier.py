"""Regression checks for the authenticated package-aware lowering frontier."""

from __future__ import annotations

import json
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/comparison/tinystories-1m-package-aware-lowering-frontier.json"


class PackageAwareLoweringFrontierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_report_is_fail_closed_and_binds_authenticated_package(self) -> None:
        self.assertEqual(self.report["schema"], "tinystories-1m-package-aware-lowering-frontier-v1")
        self.assertEqual(self.report["status"], "unsupported")
        self.assertEqual(len(self.report["contract_sha256"]), 64)
        self.assertEqual(set(self.report["package"]), {
            "manifest_sha256", "receipt_sha256", "weights_sha256",
            "scales_sha256", "calibration_ids_sha256",
        })
        unsigned = {key: value for key, value in self.report.items() if key != "sha256"}
        self.assertEqual(
            self.report["sha256"],
            hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        )

    def test_stage_chain_has_recorded_hashes_and_sizes(self) -> None:
        stages = self.report["stages"]
        self.assertEqual(list(stages), ["exported_program", "torch_mlir", "linalg", "scf", "flat_scf", "pre_calyx"])
        for stage in stages.values():
            self.assertGreater(stage["bytes"], 0)
            self.assertRegex(stage["sha256"], r"^[0-9a-f]{64}$")

    def test_frontier_records_both_exact_backend_boundaries(self) -> None:
        frontier = self.report["frontier"]
        self.assertEqual(frontier["unmodified_circt"]["operation"], "arith.uitofp")
        self.assertEqual(frontier["unmodified_circt"]["source_line"], 337)
        self.assertEqual(frontier["existing_pre_calyx_passes"]["status"], "succeeded")
        self.assertEqual(frontier["next_circt"]["operation"], "math.exp")
        self.assertEqual(frontier["next_circt"]["semantic_role"], "attention softmax")
        self.assertEqual(frontier["next_circt"]["source_line"], 830)

    def test_no_downstream_success_is_claimed(self) -> None:
        claims = self.report["claims"]
        self.assertTrue(all(value is False for value in claims.values()))
        self.assertIn("no equivalence", self.report["note"])


if __name__ == "__main__":
    unittest.main()
