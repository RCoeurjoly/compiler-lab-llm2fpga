import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RcServingW4A8IntegratedNixTest(unittest.TestCase):
    def test_integrated_system_materializes_one_export(self) -> None:
        source = (ROOT / "nix/rc-serving-w4a8-integrated-system.nix").read_text()
        self.assertIn("materialize_rc_serving_w4a8_integrated.py", source)
        self.assertIn("--phase-oracle", source)
        self.assertIn("exportedProgramCount = 1", source)
        self.assertIn("preferLocalBuild = true", source)
        self.assertIn("allowSubstitutes = false", source)
        self.assertNotIn("prefill8PytorchExported", source)
        self.assertNotIn("decode8PytorchExported", source)
        self.assertNotIn("decode9PytorchExported", source)
        self.assertNotIn("rcServingW4A8Registry", source)

    def test_flake_exports_integrated_reference_and_program(self) -> None:
        source = (ROOT / "flake.nix").read_text()
        self.assertIn("rcServingW4A8IntegratedSystem", source)
        self.assertIn(
            '"tinystories-w4a8-rc-serving-integrated-reference"', source
        )
        self.assertIn(
            '"tinystories-w4a8-rc-serving-integrated-pytorch-exported"', source
        )


if __name__ == "__main__":
    unittest.main()
