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
        flake = read("flake.nix")
        models = read("nix/models.nix")
        materializer = read("scripts/materialize-pytorch-exported.py")

        self.assertIn("materialize-pytorch-exported.py", flake)
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
        self.assertFalse(
            (REPO_ROOT / "scripts/diagnostics/scf_to_calyx_no_handshake.sh").exists()
        )
        self.assertFalse(
            (REPO_ROOT / "scripts/diagnostics/calyx_to_sv_no_handshake.sh").exists()
        )

    def test_pipeline_aliases_are_generated_from_metadata(self) -> None:
        flake = read("flake.nix")

        self.assertIn("pipelineAliasSpecs", flake)
        self.assertIn("mkPipelineAliases", flake)
        self.assertIn("model = \"tinystories-representative-core-w4a8\"", flake)
        self.assertIn("frontend = \"tosa\"", flake)
        self.assertIn("backend = \"calyx-sv\"", flake)
        self.assertNotIn("viaTosaLinearW4A8PipelinePackages = {", flake)

    def test_active_pipeline_variants_are_exported_as_json(self) -> None:
        flake = read("flake.nix")

        self.assertIn("activePipelineVariantsJson", flake)
        self.assertIn("active-pipeline-variants", flake)
        self.assertIn("active-pipeline-variants.json", flake)
        self.assertIn("schemaVersion = 1", flake)
        self.assertIn("builtins.toJSON", flake)
        self.assertIn("generatedAliases", flake)

    def test_read_the_repo_doc_points_to_core_files_in_order(self) -> None:
        doc = read("docs/read-the-repo.md")

        expected = [
            "docs/pipeline-contract.md",
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


if __name__ == "__main__":
    unittest.main()
