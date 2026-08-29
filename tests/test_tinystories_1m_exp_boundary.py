"""Tests for the fail-closed TinyStories-1M exp boundary diagnostic."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/diagnose_tinystories_1m_exp_boundary.py"
REPORT = ROOT / "artifacts/comparison/tinystories-1m-exp-lowering-boundary.json"


def load_module():
    spec = importlib.util.spec_from_file_location("tinystories_exp_boundary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyStoriesExpBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.module = load_module()

    def test_report_is_canonical_and_fail_closed(self):
        report = self.report
        unsigned = {key: value for key, value in report.items() if key != "sha256"}
        self.assertEqual(report["schema"], "tinystories-1m-exp-lowering-boundary-v1")
        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["sha256"], self.module.canonical_sha256(unsigned))
        self.assertFalse(report["decision"]["lowering_applied"])
        self.assertFalse(report["decision"]["equivalence_claim"])

    def test_exact_boundary_and_required_contract_are_explicit(self):
        boundary = self.report["boundary"]
        self.assertEqual(boundary["first_unsupported_operation"], "math.exp")
        self.assertEqual(boundary["location"], "pre-Calyx flat-SCF artifact line 830")
        required = boundary["required_contract"]
        self.assertTrue(required)
        self.assertTrue(all(value is None for value in required.values()))

    def test_inventory_does_not_promote_approximation(self):
        candidates = self.report["candidate_inventory"]
        self.assertGreaterEqual(len(candidates), 3)
        self.assertNotIn("accepted", {item["status"] for item in candidates})
        self.assertTrue(any(item["reason_code"] == "approximation_not_exact" for item in candidates))

    def test_f32_reference_vectors_are_reproducible(self):
        for vector in self.report["reference_vectors"]["vectors"]:
            expected = self.module.exact_f32_exp(vector["input"])
            self.assertEqual(vector["reference_output_bits"], self.module.bits(expected))
            self.assertEqual(vector["input_bits"], self.module.bits(vector["input"]))

    def test_context_parser_requires_max_subtract_and_reduction(self):
        text = "\n".join([
            "%score_delta = arith.subf %raw, %row_max : f32",
            "memref.store %score_delta, %scores[%i] : memref<8xf32>",
            "%padding = arith.addi %i, %one : index",
            "%score = memref.load %scores[%i] : memref<8xf32>",
            "%exp = math.exp %score : f32",
            "memref.store %exp, %scores[%i] : memref<8xf32>",
            "%sum = arith.addf %acc, %exp : f32",
        ])
        context = self.module.discover_softmax_exp_context(text)
        self.assertEqual(context["source_line"], 5)
        self.assertEqual(context["exp_operand"], "%score")
        self.assertIn("arith.subf", context["max_subtract"])
        self.assertEqual(context["max_subtract_line"], 1)
        self.assertEqual(context["reduction_line"], 7)
        with self.assertRaisesRegex(ValueError, "score memref reload"):
            self.module.discover_softmax_exp_context("%exp = math.exp %x : f32")

    def test_frontier_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "artifacts/comparison"
            target.mkdir(parents=True)
            source = ROOT / "artifacts/comparison/tinystories-1m-package-aware-lowering-frontier.json"
            altered = json.loads(source.read_text(encoding="utf-8"))
            altered["model"] = "substitute"
            (target / source.name).write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "file hash mismatch"):
                self.module.load_frontier(root)

    def test_dense_non_exp_line_is_ignored(self):
        dense = "resource " + ("x" * 1_000_000)
        with self.assertRaisesRegex(ValueError, "no f32 math.exp"):
            self.module.discover_softmax_exp_context(dense)


if __name__ == "__main__":
    unittest.main()
