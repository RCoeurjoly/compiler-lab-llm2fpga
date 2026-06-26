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


if __name__ == "__main__":
    unittest.main()
