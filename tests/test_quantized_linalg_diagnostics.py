import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "pipeline" / "diagnose_quantized_linalg.py"


class QuantizedLinalgDiagnosticsTest(unittest.TestCase):
    def run_diagnostic(self, mlir: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mlir"
            output_path = Path(tmp) / "report.json"
            input_path.write_text(mlir, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--stage",
                    "test-linalg",
                    "--input",
                    str(input_path),
                    "--out",
                    str(output_path),
                    "--fail-on-float-after-quantized-matmul",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result, json.loads(output_path.read_text(encoding="utf-8"))

    def test_fails_on_float_requant_after_quantized_matmul(self) -> None:
        result, report = self.run_diagnostic(
            """
            %0 = linalg.quantized_matmul ins(%a, %b, %azp, %bzp : tensor<1x8xi8>, tensor<8x4xi8>, i32, i32) outs(%acc : tensor<1x4xi32>) -> tensor<1x4xi32>
            %1 = arith.sitofp %0 : i32 to f32
            %2 = arith.mulf %1, %scale : f32
            """
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report["stage"], "test-linalg")
        self.assertTrue(report["saw_quantized_matmul"])
        self.assertEqual(report["hard_failures"][0]["kind"], "float-after-quantized-matmul")
        self.assertEqual(report["float_ops_after_quantized_matmul"][0]["op"], "arith.sitofp")

    def test_passes_integer_post_matmul_path(self) -> None:
        result, report = self.run_diagnostic(
            """
            %0 = linalg.quantized_matmul ins(%a, %b, %azp, %bzp : tensor<1x8xi8>, tensor<8x4xi8>, i32, i32) outs(%acc : tensor<1x4xi32>) -> tensor<1x4xi32>
            %1 = arith.addi %0, %bias : i32
            %2 = arith.muli %1, %multiplier : i32
            %3 = arith.shrsi %2, %shift : i32
            %4 = arith.trunci %3 : i32 to i8
            """
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report["saw_quantized_matmul"])
        self.assertEqual(report["hard_failures"], [])
        self.assertEqual(report["float_ops_after_quantized_matmul"], [])

    def test_flake_exposes_pattern_linear_w4a8_linalg_diagnostic_gate(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("pattern-linear-w4a8-linalg-diagnostics", flake)
        self.assertIn("diagnose_quantized_linalg.py", flake)
        self.assertIn("pattern-linear-w4a8-linalg", flake)

    def test_flake_exposes_pattern_linear_w4a8_tosa_experiment(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("pattern-linear-w4a8-tosa.mlir", flake)
        self.assertIn("--torch-backend-to-tosa-backend-pipeline", flake)
        self.assertIn("pattern-linear-w4a8-torch", flake)

    def test_torch_mlir_build_uses_upstream_without_local_patches(self) -> None:
        torch_mlir = (REPO_ROOT / "torch-mlir.nix").read_text(encoding="utf-8")

        self.assertIn("patches = [ ];", torch_mlir)
        self.assertNotIn("applyTask3RfpPatches", torch_mlir)
        self.assertNotIn("task3RfpPatches", torch_mlir)
        self.assertNotIn("task6Patches", torch_mlir)

    def test_flake_does_not_expose_patched_torch_mlir_variants(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertNotIn("torchMlirPatched", flake)
        self.assertNotIn("pipelineLibPatched", flake)
        self.assertNotIn("pipelineLibTosaPatched", flake)
        self.assertNotIn("-patched", flake)

    def test_local_patch_stacks_are_archived_and_not_part_of_active_pipeline(self) -> None:
        archive = REPO_ROOT / "archive" / "patches" / "unused"
        readme = (archive / "README.md").read_text(encoding="utf-8").lower()

        self.assertFalse((REPO_ROOT / "patches").exists())
        self.assertTrue((archive / "torch-mlir-task3-rfp").exists())
        self.assertTrue((archive / "torch-mlir-task6").exists())
        self.assertTrue((archive / "circt-upstream-task3-recovery").exists())
        self.assertIn("not applied", readme)
        self.assertIn("historical reference", readme)

    def test_tosa_pipeline_rejoins_sv_path(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        tosa_to_linalg = REPO_ROOT / "scripts" / "pipeline" / "tosa_to_linalg.sh"

        self.assertTrue(tosa_to_linalg.exists())
        self.assertIn("--tosa-to-linalg-pipeline", tosa_to_linalg.read_text(encoding="utf-8"))
        self.assertIn("--tosa-to-arith='include-apply-rescale'", tosa_to_linalg.read_text(encoding="utf-8"))
        self.assertIn("registerTosaModel", pipeline)
        self.assertIn("mkTosaToLinalgDerivation", pipeline)
        self.assertIn("pipelineLibTosa", flake)
        self.assertIn("tosaToLinalgMlir = mlirForTorchMlir", flake)
        self.assertIn("mkPipelineAliases", flake)
        self.assertIn('alias = "pattern-linear-w4a8-via-tosa"', flake)
        self.assertIn('alias = "pattern-linear-w4a8-core-via-tosa"', flake)
        self.assertIn('"tinystories-representative-core-w4a8-via-tosa-no-handshake"', flake)
        for stage in ["cf", "hw0", "sv", "calyx-sv"]:
            self.assertIn(f'"{stage}"', flake)

    def test_tosa_no_handshake_pipeline_is_public_and_skips_handshake_tail(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")

        self.assertIn("registerTosaNoHandshakeModel", pipeline)
        self.assertIn("mkNoHandshakePipeline", pipeline)
        self.assertIn("mkLinalgToScfDerivation", pipeline)
        self.assertIn("mkScfToFlatScfDerivation", pipeline)
        self.assertIn("mkScfToCalyxDerivation", pipeline)
        self.assertIn("mkLinalgToLlvmDerivation", pipeline)
        self.assertIn("noHandshakeScfToFlatScf", pipeline)
        self.assertIn("flatScfBlockerReport", pipeline)
        self.assertIn("FLAT_SCF_BLOCKER_REPORT", pipeline)
        self.assertIn("flatScf = self.\"flat-scf\"", pipeline)
        self.assertIn("model.calyx.mlir", pipeline)
        self.assertIn("manifest.json", pipeline)
        self.assertIn("scf_to_flat_scf_no_handshake.sh", flake)
        self.assertIn("flat_scf_blocker_report.py", flake)
        self.assertIn('alias = "pattern-linear-w4a8-core-via-tosa-no-handshake"', flake)
        self.assertIn('model = "pattern-linear-w4a8-core"', flake)
        self.assertIn('backend = "calyx-sv"', flake)
        for stage in ["scf", "flat-scf", "calyx", "calyx-sv", "llvm"]:
            self.assertIn(f'"{stage}"', flake)
        self.assertIn("mkCalyxSvDerivation", pipeline)
        self.assertIn('"calyx-sv"', pipeline)
        self.assertIn('"tinystories-representative-core-w4a8-via-tosa-no-handshake"', flake)
        self.assertIn('model = "tinystories-representative-core-w4a8"', flake)

    def test_flat_scf_stage_does_not_rewrite_mlir_text_with_embedded_python(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "pipeline" / "scf_to_flat_scf_no_handshake.sh"
        ).read_text(encoding="utf-8")

        self.assertNotIn("python3 -", script)
        self.assertNotIn("COPY_RE", script)
        self.assertNotIn("memref.load {src}", script)
        self.assertNotIn("memref.store {value}", script)

    def test_representative_core_adapter_removes_hf_rank4_attention_bias(self) -> None:
        adapter = (
            REPO_ROOT
            / "TinyStories"
            / "model_adapter_representative_core_pt2e_static_quant.py"
        ).read_text(encoding="utf-8")

        self.assertIn("replace_attention_with_hardware_friendly_attention", adapter)
        self.assertIn("disable_single_token_causal_mask", adapter)
        self.assertNotIn("attn.attention.bias", adapter)

    def test_representative_core_adapter_uses_int8_embedding_lookup(self) -> None:
        adapter = (
            REPO_ROOT
            / "TinyStories"
            / "model_adapter_representative_core_pt2e_static_quant.py"
        ).read_text(encoding="utf-8")

        self.assertIn("class Int8Embedding", adapter)
        self.assertIn("replace_embeddings_with_int8_lookup", adapter)
        self.assertIn("torch.int8", adapter)
        self.assertIn("F.embedding", adapter)
        self.assertIn("replace_embeddings_with_int8_lookup(model)", adapter)


if __name__ == "__main__":
    unittest.main()
