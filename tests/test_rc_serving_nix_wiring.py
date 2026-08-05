import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEY = "tinystories-w8a8-rc-serving-mask10-vocab6-width2"


class RcServingNixWiringTest(unittest.TestCase):
    def test_dedicated_system_keeps_serving_bundle_out_of_generic_registry(self) -> None:
        system = (ROOT / "nix" / "rc-serving-system.nix").read_text(
            encoding="utf-8"
        )
        models = (ROOT / "nix" / "models.nix").read_text(encoding="utf-8")
        pipeline = (ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        self.assertIn(KEY, system)
        self.assertIn("directExportBundle", system)
        self.assertIn("prefill8PytorchExported", system)
        self.assertIn("decode8PytorchExported", system)
        self.assertIn("decode9PytorchExported", system)
        self.assertNotIn(KEY, models)
        self.assertNotIn(KEY, pipeline)

    def test_flake_exposes_only_named_source_and_phase_artifacts(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn("rcServingSystem", flake)
        self.assertIn(KEY + "-native-reference", flake)
        self.assertIn(KEY + "-direct-export-bundle", flake)
        self.assertIn(KEY + "-prefill-8-pytorch-exported", flake)
        self.assertIn(KEY + "-decode-8-pytorch-exported", flake)
        self.assertIn(KEY + "-decode-9-pytorch-exported", flake)
        self.assertNotIn(KEY + "-torch", flake)


if __name__ == "__main__":
    unittest.main()
