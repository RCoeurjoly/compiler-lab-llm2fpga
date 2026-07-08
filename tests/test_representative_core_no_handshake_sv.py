import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RepresentativeCoreNoHandshakeSvTest(unittest.TestCase):
    def test_representative_core_has_explicit_no_handshake_calyx_sv_target(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn(
            '"tinystories-representative-core-w4a8-via-tosa-no-handshake"',
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

    def test_representative_core_has_direct_linalg_no_handshake_calyx_sv_target(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn(
            '"tinystories-representative-core-w4a8-via-linalg-no-handshake"',
            flake,
        )
        self.assertIn('frontend = "linalg"', flake)
        self.assertIn('backend = "calyx-sv"', flake)
        self.assertIn("pipelineStagePackagesNoHandshake", flake)

    def test_calyx_sv_script_does_not_use_handshake(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "pipeline" / "calyx_to_sv_no_handshake.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("--lower-calyx-to-hw", script)
        self.assertIn("--lower-hw-to-sv", script)
        self.assertIn("--export-verilog", script)
        self.assertNotIn("handshake", script.lower())

    def test_flat_scf_stage_uses_mlir_flatten_memref_for_expand_shape_reproducer(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "diagnostics" / "scf_to_flat_scf_no_handshake.sh"
        ).read_text(encoding="utf-8")
        reproducer = (
            REPO_ROOT
            / "reproducers"
            / "flat-scf-expand-shape-materialization"
            / "input.mlir"
        )

        self.assertTrue(reproducer.exists())
        self.assertIn("mlir_opt=", script)
        self.assertIn("--flatten-memref", script)
        self.assertIn("--lower-affine", script)
        self.assertNotIn("circt_opt=", script)

    def test_no_handshake_bufferization_uses_identity_layout_boundaries(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "diagnostics" / "linalg_to_scf_no_handshake.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("--one-shot-bufferize=", script)
        self.assertIn("bufferize-function-boundaries", script)
        self.assertIn("function-boundary-type-conversion=identity-layout-map", script)

    def test_pre_calyx_uses_checked_in_mlir_pass_plugin(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        pass_source = (
            REPO_ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpgaMlirPasses", flake)
        self.assertIn("inherit mlir llvmPackages", flake)
        self.assertIn("--load-pass-plugin=${mlirPasses}", pipeline)
        self.assertIn("llm2fpga-fold-constant-truncf", pipeline)
        self.assertIn("PassRegistration<FoldConstantTruncFOpsPass>", pass_source)
        self.assertNotIn("python3 -", pipeline)

    def test_current_calyx_truncf_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-arith-truncf-constant"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        passing_shape = (reproducer_dir / "f32-constant.mlir").read_text(
            encoding="utf-8"
        )
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("arith.truncf", failing)
        self.assertIn(": f64 to f32", failing)
        self.assertIn("arith.constant 1.000000e-05 : f32", passing_shape)
        self.assertIn("Do not fix this with textual MLIR rewriting", readme)


if __name__ == "__main__":
    unittest.main()
