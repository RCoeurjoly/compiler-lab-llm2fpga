import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CALYX_REV = "5a4303847392609cad83dda6f4bdffc8cc0e5c89"
HARDFLOAT_HASH = "sha256-azdXyfv6IjDGorhGBeOTcstYnddQDpecTwuOzIoDsUs="
DAP_GIT_HASH = "sha256-oJHeY9Hm8DMC1T9flRyjf6EmBcJc3tuvcPlZXtHTGqs="


class CalyxFloatNixPackageTest(unittest.TestCase):
    def test_pinned_upstream_calyx_and_hardfloat_are_declared(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        calyx = (ROOT / "nix" / "calyx.nix").read_text(encoding="utf-8")
        hardfloat = (ROOT / "nix" / "hardfloat.nix").read_text(encoding="utf-8")

        self.assertIn('calyx-src = {', flake)
        self.assertIn(f'github:calyxir/calyx/{CALYX_REV}', flake)
        self.assertIn('flake = false;', flake)
        self.assertIn('pkgsLlvm21.callPackage ./nix/hardfloat.nix', flake)
        self.assertIn('pkgsLlvm21.callPackage ./nix/calyx.nix', flake)
        self.assertIn('calyxSrc = inputs.calyx-src;', flake)
        self.assertIn('src = calyxSrc;', calyx)
        self.assertIn('cargoLock = {', calyx)
        self.assertIn('lockFile = "${calyxSrc}/Cargo.lock";', calyx)
        self.assertIn('"https://github.com/rust-lang/crates.io-index"', calyx)
        self.assertIn('"https://static.crates.io/crates"', calyx)
        self.assertIn(f'"dap-0.4.1-alpha1" = "{DAP_GIT_HASH}";', calyx)
        self.assertIn('preBuild = \'\'', calyx)
        self.assertIn('$0 ~ /^\\[source\\./ && state == 1', calyx)
        self.assertIn('checking for redundant crates.io source stanza', calyx)
        self.assertIn('removed redundant crates.io source stanza', calyx)
        self.assertNotIn('cargoHash', calyx)
        self.assertNotIn('crates.io/api/v1/crates', calyx)
        self.assertIn('HardFloat-1', calyx)
        self.assertIn('primitives/float/HardFloat-1', calyx)
        self.assertIn(HARDFLOAT_HASH, hardfloat)
        self.assertNotIn('get_hardfloat.sh', calyx)
        self.assertNotIn('curl', hardfloat)

    def test_float_reproducer_and_native_selftest_are_declared(self) -> None:
        fixture = (ROOT / "reproducers/calyx-float-library-selftest/input.futil")
        readme = (ROOT / "reproducers/calyx-float-library-selftest/README.md")
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertTrue(fixture.exists())
        self.assertTrue(readme.exists())
        source = fixture.read_text(encoding="utf-8")
        readme_text = readme.read_text(encoding="utf-8")
        self.assertIn('import "primitives/float/addFN.futil";', source)
        self.assertIn('std_addFN(8, 24, 32)', source)
        self.assertIn("library closure", readme_text)
        self.assertIn("not numerical-equivalence evidence", readme_text)
        self.assertIn('calyx-float-library-selftest', flake)
        self.assertIn('module std_addFN', flake)
        self.assertIn('module fNToRecFN', flake)
        self.assertIn('yosysSlang', flake)

    def test_float_exports_use_the_tested_main_sv_closure(self) -> None:
        script = (ROOT / "scripts/pipeline/calyx_to_sv_no_handshake.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('primitives/float/*', script)
        self.assertIn('"$output_dir/sv/main.sv" >"$output_dir/sources.f"', script)
        self.assertNotIn('mktemp /tmp/calyx_', script)


if __name__ == "__main__":
    unittest.main()
