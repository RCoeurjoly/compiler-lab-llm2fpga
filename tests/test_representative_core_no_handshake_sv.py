import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RepresentativeCoreNoHandshakeSvTest(unittest.TestCase):
    def test_representative_core_has_explicit_no_handshake_calyx_sv_target(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn(
            'alias = "tinystories-representative-core-w4a8-via-tosa-no-handshake"',
            flake,
        )
        self.assertIn('model = "tinystories-representative-core-w4a8"', flake)
        self.assertIn('frontend = "tosa"', flake)
        self.assertIn('backend = "calyx-sv"', flake)
        self.assertIn('"calyx-sv"', flake)
        self.assertIn("calyxToSvNoHandshake", flake)
        self.assertNotIn(
            'pipelineStagePackagesTosaPatched."tinystories-representative-core-w4a8-sv"',
            flake,
        )

    def test_calyx_sv_script_does_not_use_handshake(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "pipeline" / "calyx_to_sv_no_handshake.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("--lower-calyx-to-hw", script)
        self.assertIn("--lower-hw-to-sv", script)
        self.assertIn("--export-verilog", script)
        self.assertNotIn("handshake", script.lower())


if __name__ == "__main__":
    unittest.main()
