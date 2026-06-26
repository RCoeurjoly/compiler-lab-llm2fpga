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


if __name__ == "__main__":
    unittest.main()
