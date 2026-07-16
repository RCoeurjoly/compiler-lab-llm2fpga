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
        binding_section = flake.split(
            "calyxRcBasicFloatBindingsSelftest = pkgs.runCommand", 1
        )[1].split("calyxIntegerLibrarySelftest = pkgs.runCommand", 1)[0]
        self.assertIn(
            're.search(r"module\\s+" + re.escape(module) + r"\\b", source)',
            binding_section,
        )
        self.assertNotIn("grep -q 'module std_addFN'", flake)
        self.assertNotIn("grep -q 'module fNToRecFN'", flake)
        self.assertIn('${yosysPkg}/bin/yosys \\', flake)
        self.assertIn('-m ${yosysSlang}/share/yosys/plugins/slang.so \\', flake)
        self.assertIn('read_slang --threads 1 --no-proc --max-parse-depth 20000 --top main $out/main.sv', flake)
        self.assertIn('hierarchy -top main -check', flake)
        self.assertIn('"calyx-float-library" = calyxFloatLibrarySelftest;', flake)

    def test_basic_float_binding_fixture_covers_every_rc_wrapper(self) -> None:
        fixture = ROOT / "reproducers/calyx-rc-basic-float-bindings/input.futil"
        readme = ROOT / "reproducers/calyx-rc-basic-float-bindings/README.md"

        self.assertTrue(fixture.exists())
        self.assertTrue(readme.exists())
        source = fixture.read_text(encoding="utf-8")
        readme_text = readme.read_text(encoding="utf-8")
        for primitive in (
            "primitives/float/addFN.futil",
            "primitives/float/mulFN.futil",
            "primitives/float/divSqrtFN.futil",
            "primitives/float/compareFN.futil",
            "primitives/float/intToFp.futil",
            "primitives/float/fpToInt.futil",
        ):
            self.assertIn(f'import "{primitive}";', source)
        for instantiation in (
            "std_addFN(8, 24, 32)",
            "std_mulFN(8, 24, 32)",
            "std_divSqrtFN(8, 24, 32)",
            "std_compareFN(8, 24, 32)",
            "std_intToFp(32, 8, 24, 32)",
            "std_fpToInt(8, 24, 32, 8)",
        ):
            self.assertIn(instantiation, source)
        self.assertIn(
            "not numerical-equivalence evidence", " ".join(readme_text.split())
        )

    def test_hardfloat_binding_derivation_is_declared(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("calyx-rc-basic-float-bindings-selftest", flake)
        self.assertIn("tinystories-w8a8-rc-calyx-hardfloat-bindings", flake)
        self.assertIn("run_rc_calyx_hardfloat_bindings.py", flake)
        for filename in (
            "addf-f32.mlir",
            "subf-f32.mlir",
            "mulf-f32.mlir",
            "divf-f32.mlir",
            "cmpf-ugt-f32.mlir",
            "sitofp-i32-f32.mlir",
            "fptosi-f32-i8.mlir",
            "uitofp-i1-f32.mlir",
        ):
            self.assertIn(filename, flake)
        self.assertIn("calyx_to_sv_no_handshake.sh", flake)
        self.assertIn("yosysSlang", flake)
        closure_section = flake.split(
            "calyxRcBasicFloatBindingsSelftest = pkgs.runCommand", 1
        )[1].split("calyxIntegerLibrarySelftest = pkgs.runCommand", 1)[0]
        self.assertIn("--allow-merging-ansi-ports", closure_section)
        evidence_section = flake.split(
            "rcCalyxHardfloatBindings = pkgs.runCommand", 1
        )[1].split("activePipelineVariantsJson", 1)[0]
        self.assertIn(
            "--calyx-to-sv-script ${pipelineScripts}/calyx_to_sv_no_handshake.sh",
            evidence_section,
        )
        self.assertIn(
            're.search(r"module\\s+" + re.escape(module) + r"\\b", source)',
            closure_section,
        )

    def test_basic_float_binding_fixture_uses_calyx_decimal_ieee_literals(self) -> None:
        source = (
            ROOT / "reproducers/calyx-rc-basic-float-bindings/input.futil"
        ).read_text(encoding="utf-8")

        self.assertNotIn("32'h", source)
        self.assertIn("32'd1065353216", source)
        self.assertIn("32'd1073741824", source)

    def test_integer_reproducer_and_native_selftest_are_declared(self) -> None:
        fixture = (ROOT / "reproducers/calyx-integer-library-selftest/input.futil")
        readme = (ROOT / "reproducers/calyx-integer-library-selftest/README.md")
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertTrue(fixture.exists())
        self.assertTrue(readme.exists())
        source = fixture.read_text(encoding="utf-8")
        readme_text = readme.read_text(encoding="utf-8")
        self.assertIn('import "primitives/core.futil";', source)
        self.assertIn('add = std_add(32);', source)
        self.assertIn("library closure", readme_text)
        self.assertIn("not numerical-equivalence evidence", readme_text)
        self.assertIn('calyxIntegerLibrarySelftest = pkgs.runCommand', flake)
        self.assertIn('"calyx-integer-library-selftest"', flake)
        self.assertIn(
            '${./reproducers/calyx-integer-library-selftest/input.futil} \\', flake
        )
        self.assertIn('for module in ("std_add", "std_reg"):', flake)
        self.assertIn('"calyx-integer-library" = calyxIntegerLibrarySelftest;', flake)

    def test_native_exports_use_the_tested_main_sv_closure(self) -> None:
        script = (ROOT / "scripts/pipeline/calyx_to_sv_no_handshake.sh").read_text(
            encoding="utf-8"
        )
        pipeline = (ROOT / "nix/pipeline.nix").read_text(encoding="utf-8")

        self.assertIn('printf \'%s\\n\' "$output_dir/sv/main.sv" >"$output_dir/sources.f"', script)
        self.assertNotIn('uses_float_extern', script)
        self.assertNotIn('CALYX_COMPILE_PRIMITIVES_TO_SV', script)
        self.assertNotIn('calyx_compile_primitives_to_sv.py', script)
        self.assertNotIn('compile.futil', script)
        self.assertNotIn('compile.sv', script)
        self.assertNotIn('primitives/core.sv', script)
        self.assertNotIn('primitives/binary_operators.sv', script)
        self.assertNotIn('primitives/memories/seq.sv', script)
        self.assertNotIn('CALYX_COMPILE_PRIMITIVES_TO_SV', pipeline)
        self.assertFalse(
            (ROOT / "scripts/pipeline/calyx_compile_primitives_to_sv.py").exists()
        )
        self.assertNotIn('mktemp /tmp/calyx_', script)

    def test_math_exp_reproducer_records_zero_exit_as_invalid_lowering(self) -> None:
        fixture = ROOT / "reproducers" / "calyx-math-exp" / "input.mlir"
        readme = ROOT / "reproducers" / "calyx-math-exp" / "README.md"
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertTrue(fixture.exists())
        self.assertIn("math.exp", fixture.read_text(encoding="utf-8"))
        self.assertIn(
            "emits no MLIR `error:` diagnostic", readme.read_text(encoding="utf-8")
        )
        self.assertIn('calyxMathExpUpstreamReproducer = pkgs.runCommand', flake)
        self.assertIn('test "$rc" -eq 0', flake)
        self.assertIn('printf \'%s\\n\' "$rc" >"$out/exit-code.txt"', flake)
        self.assertIn('"valid_lowering": false', flake)
        self.assertIn('"exit_code_observed": 0', flake)


if __name__ == "__main__":
    unittest.main()
