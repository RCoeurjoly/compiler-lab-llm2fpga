import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class FullTinyStoriesW8A8ScoutTest(unittest.TestCase):
    def test_full_model_w8a8_is_registered_with_existing_pt2e_adapter(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")

        match = re.search(
            r'"tinystories-w8a8" = registerModel \{.*?^  \};',
            models,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        block = match.group(0)

        self.assertIn('quantization = "pt2e-static-w8a8"', block)
        self.assertIn("model_adapter_pt2e_static_quant.py", block)
        self.assertIn("hfSnapshot = tinyStories1m.snapshot", block)
        self.assertIn("pythonWithTinyStoriesTorchAO", block)

    def test_full_model_w8a8_has_public_tosa_no_handshake_alias(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        match = re.search(
            r'alias = "tinystories-w8a8-via-tosa-no-handshake";.*?^          \}',
            flake,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        block = match.group(0)

        self.assertIn('model = "tinystories-w8a8"', block)
        self.assertIn("packages = pipelineStagePackagesTosaNoHandshake", block)
        self.assertIn("stages = noHandshakeStages", block)


if __name__ == "__main__":
    unittest.main()
