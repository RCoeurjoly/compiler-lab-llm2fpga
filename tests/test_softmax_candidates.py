import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("softmax_candidates", ROOT / "scripts/pipeline/evaluate_softmax_candidates.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["softmax_candidates"] = module
spec.loader.exec_module(module)


class SoftmaxCandidateTests(unittest.TestCase):
    def test_exact_streaming_matches_reference(self):
        result = module.evaluate([[0.0, -0.5, -1.0, -2.0, -4.0, -8.0]])
        candidate = result["candidates"]["streaming-exact"]
        self.assertEqual(candidate["max_abs_softmax_error"], 0.0)
        self.assertTrue(candidate["rows_sum_to_one"])

    def test_approximate_candidates_have_explicit_finite_contract(self):
        result = module.evaluate([[0.0, -0.5, -1.0, -2.0, -4.0, -8.0]])
        for name in ("lut-256", "polynomial-5", "cordic-12"):
            self.assertTrue(result["candidates"][name]["finite"])
            self.assertTrue(result["candidates"][name]["rows_sum_to_one"])
            self.assertGreaterEqual(result["candidates"][name]["max_abs_softmax_error"], 0.0)


if __name__ == "__main__":
    unittest.main()
