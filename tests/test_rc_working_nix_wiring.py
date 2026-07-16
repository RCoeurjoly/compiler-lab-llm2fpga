import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FLAKE = REPO_ROOT / "flake.nix"
RC_SYSTEM = REPO_ROOT / "nix" / "rc-working-system.nix"


class RcWorkingNixWiringTest(unittest.TestCase):
    def test_working_alias_points_to_the_existing_structural_finalist(self) -> None:
        flake = FLAKE.read_text(encoding="utf-8")

        self.assertIn('alias = "tinystories-w8a8-rc-working-via-linalg-no-handshake"', flake)
        self.assertIn(
            'model = "tinystories-w8a8-rc-study-mask9-vocab6-width2"', flake
        )
        self.assertIn('frontend = "linalg"', flake)
        self.assertIn(
            'pipelineStagePackagesNoHandshake."tinystories-w8a8-rc-study-mask9-vocab6-width2-pytorch-exported"',
            flake,
        )
        self.assertIn('"tinystories-w8a8-rc-reference-image"', flake)

    def test_reference_image_derivation_runs_oracle_pack_and_replay(self) -> None:
        self.assertTrue(RC_SYSTEM.exists())
        source = RC_SYSTEM.read_text(encoding="utf-8")

        self.assertIn("build_rc_working_reference.py", source)
        self.assertIn("pack_rc_working_image.py", source)
        self.assertIn("verify_rc_working_image.py", source)
        self.assertIn("source-exported-sha256.txt", source)
        self.assertIn('if [ "$status" != "pass" ]', source)
        self.assertIn("${pkgs.diffutils}/bin/cmp", source)

    def test_abi_audit_uses_the_actual_flat_scf_and_calyx_artifacts(self) -> None:
        flake = FLAKE.read_text(encoding="utf-8")
        source = RC_SYSTEM.read_text(encoding="utf-8")

        self.assertIn("audit_rc_sv_interface.py", source)
        self.assertIn("flatScf}/flat.scf.mlir", source)
        self.assertIn("calyx}/manifest.json", source)
        self.assertIn("lower-scf-to-calyx.log", source)
        self.assertIn("interface.json", source)
        self.assertIn("tinystories-w8a8-rc-abi-audit", flake)


if __name__ == "__main__":
    unittest.main()
