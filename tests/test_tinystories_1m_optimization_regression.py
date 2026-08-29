"""Fail-closed Task 4 gate for the TinyStories-1M optimization.

Task 3 did not produce an aligned comparison or a ranked waste candidate.  This
test is deliberately a regression on that boundary: it prevents Task 4 from
silently turning structural guesses into an optimization claim.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPARISON = ROOT / "artifacts/comparison/tinystories-1m-slice-comparison.json"
RESULT = ROOT / "artifacts/comparison/tinystories-1m-optimization-result.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class TinyStories1MOptimizationRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.comparison = json.loads(COMPARISON.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_task3_has_no_candidate_that_task4_can_select(self) -> None:
        self.assertIn(self.comparison["status"], {"contract_mismatch", "incomplete"})
        self.assertEqual(self.comparison["waste_map"], [])
        self.assertIsNone(self.comparison["resources"])
        self.assertIsNone(self.comparison["timing"])
        self.assertEqual(self.comparison["functional"]["checkpoint_status"], "unavailable")

    def test_optimization_result_is_explicitly_blocked(self) -> None:
        self.assertEqual(self.result["schema"], "tinystories-1m-optimization-result-v1")
        self.assertEqual(self.result["status"], "blocked_missing_evidence")
        self.assertIsNone(self.result["selected_candidate"])
        self.assertIsNone(self.result["source_change"])
        self.assertIsNone(self.result["before"])
        self.assertIsNone(self.result["after"])
        self.assertFalse(self.result["acceptance"]["functional_equivalence"])
        self.assertFalse(self.result["acceptance"]["resource_improvement"])
        self.assertFalse(self.result["acceptance"]["timing_preserved"])

    def test_blocked_result_does_not_claim_a_structural_property(self) -> None:
        self.assertEqual(self.result["candidate_status"], "none_ranked")
        self.assertIsNone(self.result["structural_property"])
        self.assertEqual(self.result["modified_paths"], [])
        self.assertGreaterEqual(len(self.result["blocking_reasons"]), 1)

    def test_result_self_hash_is_canonical(self) -> None:
        self.assertEqual(
            self.result["sha256"],
            canonical_sha256({key: value for key, value in self.result.items() if key != "sha256"}),
        )

    def test_comparison_input_hash_is_pinned(self) -> None:
        self.assertEqual(
            self.result["inputs"]["comparison"]["sha256"],
            file_sha256(COMPARISON),
        )


if __name__ == "__main__":
    unittest.main()
