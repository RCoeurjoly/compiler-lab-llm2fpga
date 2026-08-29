import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/comparison/tinystories-1m-no-handshake-calyx-frontier.json"


class TinyStories1MNoHandshakeFrontierTest(unittest.TestCase):
    def test_no_handshake_stage_is_explicitly_exported(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn(
            '"tiny-stories-1m-baseline-float-no-handshake-calyx"', flake
        )
        self.assertIn("pipelineStagePackagesNoHandshake", flake)

    def test_frontier_is_fail_closed_at_math_exp(self) -> None:
        report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "blocked_unsupported_math_exp")
        self.assertEqual(report["frontier"]["unsupported_ops"], {"math.exp": 8})
        self.assertFalse(report["claims"]["full_block_artifact"])
        self.assertFalse(report["claims"]["hardware_inference"])


if __name__ == "__main__":
    unittest.main()
