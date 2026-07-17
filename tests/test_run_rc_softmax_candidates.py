import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrozenProbeContractTests(unittest.TestCase):
    def test_probe_is_observation_only(self):
        source = (ROOT / "scripts/pipeline/run_rc_softmax_candidates.py").read_text()
        tree = ast.parse(source)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertIn("observe_rows", names)
        self.assertIn("candidate", names)
        self.assertNotIn("export", names)
        self.assertNotIn("rewrite", names)

    def test_probe_names_frozen_model_and_no_sv_claim(self):
        source = (ROOT / "scripts/pipeline/run_rc_softmax_candidates.py").read_text()
        self.assertIn("RC_WORKING_SOURCE_MODEL_KEY", source)
        self.assertIn("analysis-only", source)
        self.assertNotIn("circt-opt", source)


if __name__ == "__main__":
    unittest.main()
