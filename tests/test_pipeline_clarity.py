import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


class PipelineClarityTest(unittest.TestCase):
    def test_torch_mlir_stage_consumes_exported_program_only(self) -> None:
        pipeline = read("nix/pipeline.nix")

        self.assertNotIn("torchMlirInput", pipeline)
        self.assertNotIn("torchInputCommand", pipeline)
        self.assertNotIn("prebuiltTorchMlirInput", pipeline)
        self.assertNotIn("legacyInlineTorchCommand", pipeline)
        self.assertIn("--exported-program-dir ${pytorchExported}", pipeline)

    def test_pytorch_export_materializer_is_single_purpose(self) -> None:
        models = read("nix/models.nix")
        materializer = read("scripts/materialize-pytorch-exported.py")

        self.assertNotIn("--stage", models)
        self.assertNotIn("--stage", materializer)
        self.assertIn(
            "Materialize a serialized PyTorch ExportedProgram.", materializer
        )

    def test_pipeline_registry_has_no_stale_extension_points(self) -> None:
        pipeline = read("nix/pipeline.nix")

        self.assertNotIn("tiny-stories-1m", pipeline)
        self.assertNotIn("registerLsqModel", pipeline)
        self.assertNotIn("registerQuantizedModel", pipeline)
        self.assertNotIn("modelPipelinesFromRegistry", pipeline)

    def test_build_input_names_describe_their_scope(self) -> None:
        pipeline = read("nix/pipeline.nix")
        models = read("nix/models.nix")

        self.assertNotIn("torchInputBuildInputs", pipeline)
        self.assertNotIn("torchInputBuildInputs", models)
        self.assertIn("pytorchToolchain", pipeline)
        self.assertIn("pytorchToolchain", models)

    def test_pytorch_export_command_is_required(self) -> None:
        pipeline = read("nix/pipeline.nix")

        self.assertNotIn("pytorchExportedCommand ? null", pipeline)
        self.assertNotIn("exported program stage is not defined", pipeline)
        self.assertNotIn("command ? null", pipeline)

    def test_torch_mlir_compiler_accepts_exported_program_only(self) -> None:
        compiler = read("scripts/compile-pytorch.py")

        self.assertIn("--exported-program-dir", compiler)
        self.assertNotIn("--adapter", compiler)
        self.assertNotIn("build_mlir_module", compiler)
        self.assertNotIn("torch.export.export", compiler)
        self.assertNotIn("load_adapter", compiler)

    def test_docs_describe_current_baseline_without_local_provenance(self) -> None:
        readme = read("README.md")
        org = read("docs/llm2fpga-mlir-bringup.org")
        models = read("nix/models.nix")

        for text in [readme, org, models]:
            self.assertNotIn("task6-crisp", text)
            self.assertNotIn("~/LLM2FPGA", text)
            self.assertNotIn("Task 3-derived", text)

        self.assertIn("Current baseline", org)
        self.assertIn("Future direction", org)

    def test_no_orphan_lsq_pipeline_script_remains(self) -> None:
        self.assertFalse((REPO_ROOT / "scripts/pipeline/cf_to_handshake_lsq.sh").exists())
        self.assertFalse(
            (REPO_ROOT / "docs/superpowers/plans/2026-06-26-task3-derived-flake.md").exists()
        )

    def test_no_accelerator_manifest_contract_remains(self) -> None:
        self.assertFalse((REPO_ROOT / "scripts/pipeline/llm2fpga_model_manifest.py").exists())
        self.assertFalse(
            (REPO_ROOT / "scripts/pipeline/test_llm2fpga_model_manifest.py").exists()
        )

    def test_pipeline_contract_documents_allowed_transforms(self) -> None:
        contract = read("docs/pipeline-contract.md")

        self.assertIn("Allowed transformations", contract)
        self.assertIn("Disallowed transformations", contract)
        self.assertIn("Active pipeline variants", contract)
        self.assertIn("PyTorch quantization", contract)
        self.assertIn("MLIR/CIRCT passes", contract)
        self.assertIn("textual MLIR rewrites", contract)

    def test_unused_patch_stacks_are_archived_not_active(self) -> None:
        archive_readme = read("archive/patches/unused/README.md")

        self.assertFalse((REPO_ROOT / "patches").exists())
        self.assertTrue((REPO_ROOT / "archive/patches/unused/torch-mlir-task3-rfp").exists())
        self.assertTrue((REPO_ROOT / "archive/patches/unused/torch-mlir-task6").exists())
        self.assertTrue((REPO_ROOT / "archive/patches/unused/circt-upstream-task3-recovery").exists())
        self.assertIn("not applied", archive_readme.lower())
        self.assertIn("historical reference", archive_readme.lower())

    def test_compiler_stage_scripts_are_under_pipeline(self) -> None:
        self.assertTrue((REPO_ROOT / "scripts/pipeline/scf_to_calyx_no_handshake.sh").exists())
        self.assertTrue((REPO_ROOT / "scripts/pipeline/calyx_to_sv_no_handshake.sh").exists())
        self.assertTrue((REPO_ROOT / "scripts/pipeline/linalg_to_scf_no_handshake.sh").exists())
        self.assertTrue((REPO_ROOT / "scripts/pipeline/scf_to_flat_scf_no_handshake.sh").exists())
        self.assertTrue((REPO_ROOT / "scripts/pipeline/linalg_to_llvm_no_handshake.sh").exists())
        self.assertFalse(
            (REPO_ROOT / "scripts/diagnostics/scf_to_calyx_no_handshake.sh").exists()
        )
        self.assertFalse(
            (REPO_ROOT / "scripts/diagnostics/calyx_to_sv_no_handshake.sh").exists()
        )
        self.assertFalse(
            (REPO_ROOT / "scripts/diagnostics/linalg_to_scf_no_handshake.sh").exists()
        )
        self.assertFalse(
            (REPO_ROOT / "scripts/diagnostics/scf_to_flat_scf_no_handshake.sh").exists()
        )
        self.assertFalse(
            (REPO_ROOT / "scripts/diagnostics/linalg_to_llvm_no_handshake.sh").exists()
        )

    def test_read_the_repo_doc_points_to_core_files_in_order(self) -> None:
        doc = read("docs/read-the-repo.md")

        expected = [
            "docs/pipeline-contract.md",
            "docs/current-baseline.md",
            "docs/read-the-repo.md",
            "flake.nix",
            "nix/models.nix",
            "nix/pipeline.nix",
            "scripts/pipeline/",
            "TinyStories/model_adapter_representative_core_pt2e_static_quant.py",
            "scripts/diagnostics/",
            "tests/",
        ]
        positions = [doc.index(path) for path in expected]

        self.assertEqual(positions, sorted(positions))
        self.assertIn("active-pipeline-variants", doc)
        self.assertIn("model", doc)
        self.assertIn("frontend", doc)
        self.assertIn("backend", doc)

    def test_current_baseline_records_representative_core_w4a8_blocker(self) -> None:
        doc = read("docs/current-baseline.md")

        expected = [
            "Representative-core W4A8, TOSA no-handshake Calyx-SV",
            "tinystories-representative-core-w4a8-via-tosa-no-handshake-calyx-sv",
            "First failing stage",
            "TOSA-to-Linalg",
            "tosa.add",
            "i8",
            "No textual MLIR rewrite",
        ]

        for text in expected:
            self.assertIn(text, doc)

    def test_current_baseline_records_historical_direct_linalg_frontier(self) -> None:
        doc = read("docs/current-baseline.md")
        direct_linalg = doc[
            doc.index("## Direct-Linalg No-Handshake Follow-Up") : doc.index(
                "## Calyx Backend Naming Split"
            )
        ]

        self.assertIn(
            "reproducers/flat-scf-expand-shape-materialization/input.mlir",
            direct_linalg,
        )
        self.assertIn("mlir-opt --flatten-memref", direct_linalg)
        self.assertIn("tinystories-representative-core-w4a8-flat-scf", direct_linalg)
        self.assertIn("tinystories-representative-core-w4a8-calyx", direct_linalg)
        self.assertIn("Calyx-stage diagnostic directory", direct_linalg)
        self.assertIn("status: failed", direct_linalg)
        self.assertIn("has-unsupported-calyx-float-frontier", direct_linalg)
        self.assertIn('"unsupported_ops": {"math.rsqrt": 5}', direct_linalg)
        self.assertIn("math.rsqrt", direct_linalg)
        self.assertIn("no longer flat-SCF", direct_linalg)
        self.assertIn("historical / pre-current-source-pin", direct_linalg)
        self.assertIn("pending-rerun", direct_linalg)
        self.assertIn("Historical verified flat-SCF output", direct_linalg)
        self.assertNotIn("Current verified flat-SCF output", direct_linalg)

    def test_current_baseline_records_fixed_layernorm_frontier(self) -> None:
        doc = read("docs/current-baseline.md")
        fixed_layernorm = doc[
            doc.index("## Fixed-LayerNorm Representative-Core Follow-Up") : doc.index(
                "## Explicit-Integer Representative-Core Slice"
            )
        ]

        self.assertIn(
            "tinystories-representative-core-w4a8-fixed-layernorm-calyx",
            fixed_layernorm,
        )
        self.assertIn(
            '{"stage":"calyx","status":"ok","artifact":"model.calyx.mlir"}',
            fixed_layernorm,
        )
        self.assertIn('"status": "has-float-frontier"', fixed_layernorm)
        self.assertIn('"total_float_ops": 883', fixed_layernorm)
        self.assertIn('"total_unsupported_ops": 0', fixed_layernorm)
        self.assertIn("primitives/float/divSqrtFN.futil", fixed_layernorm)
        self.assertIn(
            "tinystories-representative-core-w4a8-fixed-layernorm-calyx-sv",
            fixed_layernorm,
        )
        self.assertIn("historical / pre-current-source-pin", fixed_layernorm)
        self.assertIn("pending-rerun", fixed_layernorm)


if __name__ == "__main__":
    unittest.main()
