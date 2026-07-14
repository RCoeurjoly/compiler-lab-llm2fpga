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
        self.assertIn('nativeBuildInputs = [ makeWrapper ];', calyx)
        self.assertIn('wrapProgram "$out/bin/calyx" \\', calyx)
        self.assertIn('--set CALYX_PRIMITIVES_DIR "$out/share/calyx"', calyx)
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
        self.assertIn('calyxFloatLibrarySelftest = pkgs.runCommand', flake)
        self.assertIn('"calyx-float-library-selftest"', flake)
        self.assertIn('${calyx}/bin/calyx \\', flake)
        self.assertIn(
            '${./reproducers/calyx-float-library-selftest/input.futil} \\', flake
        )
        self.assertIn('-l ${calyx}/share/calyx \\', flake)
        self.assertIn('nativeBuildInputs = [ calyx yosysPkg python ];', flake)
        self.assertIn('${python}/bin/python3 - "$out/main.sv" <<\'PY\'', flake)
        self.assertIn('Path(sys.argv[1]).read_text(encoding="utf-8")', flake)
        self.assertIn('for module in ("std_addFN", "fNToRecFN"):', flake)
        self.assertIn(
            're.search(r"module\\s+" + re.escape(module) + r"\\b", source)',
            flake,
        )
        self.assertNotIn("grep -q 'module std_addFN'", flake)
        self.assertNotIn("grep -q 'module fNToRecFN'", flake)
        self.assertIn('${yosysPkg}/bin/yosys \\', flake)
        self.assertIn('-m ${yosysSlang}/share/yosys/plugins/slang.so \\', flake)
        self.assertIn('"calyx-float-library" = calyxFloatLibrarySelftest;', flake)

    def test_float_exports_use_the_tested_main_sv_closure(self) -> None:
        script = (ROOT / "scripts/pipeline/calyx_to_sv_no_handshake.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('uses_float_extern=0', script)
        self.assertIn(
            'if [[ "$import_path" == primitives/float/* ]]; then', script
        )
        self.assertNotIn('primitives/float.futil', script)
        self.assertIn('if [[ "$uses_float_extern" -eq 1 ]]; then', script)
        self.assertIn('printf \'%s\\n\' "$output_dir/sv/main.sv" >"$output_dir/sources.f"', script)
        self.assertIn('"$output_dir/sv/compile.sv"', script)
        self.assertIn('$calyx_lib/primitives/core.sv', script)
        self.assertIn('$calyx_lib/primitives/binary_operators.sv', script)
        self.assertIn('$calyx_lib/primitives/memories/seq.sv', script)
        self.assertNotIn('mktemp /tmp/calyx_', script)


if __name__ == "__main__":
    unittest.main()
