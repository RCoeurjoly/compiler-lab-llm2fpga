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

    def test_torch_mlir_build_uses_upstream_without_local_patches(self) -> None:
        torch_mlir = (REPO_ROOT / "torch-mlir.nix").read_text(encoding="utf-8")

        self.assertIn("patches = [ ];", torch_mlir)
        self.assertNotIn("applyTask3RfpPatches", torch_mlir)
        self.assertNotIn("task3RfpPatches", torch_mlir)
        self.assertNotIn("task6Patches", torch_mlir)

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
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        tosa_to_linalg = REPO_ROOT / "scripts" / "pipeline" / "tosa_to_linalg.sh"
        script = tosa_to_linalg.read_text(encoding="utf-8")

        self.assertTrue(tosa_to_linalg.exists())
        self.assertIn("--load-pass-plugin", script)
        legalization = script.index("llm2fpga-legalize-pt2e-tosa-zero-point")
        validation = script.index("tosa-validate")
        lowering = script.index("tosa-to-linalg-pipeline")
        self.assertLess(legalization, validation)
        self.assertLess(validation, lowering)
        self.assertIn("--tosa-to-arith='include-apply-rescale'", script)
        self.assertIn("${mlirPasses}/lib/LLM2FPGAMLIRPasses.so", pipeline)
        self.assertIn("registerTosaModel", pipeline)
        self.assertIn("mkTosaToLinalgDerivation", pipeline)

    def test_tosa_no_handshake_pipeline_is_public_and_skips_handshake_tail(self) -> None:
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
        self.assertIn("mkCalyxNativeSvDerivation", pipeline)
        self.assertIn("mkCalyxHwSvDerivation", pipeline)
        self.assertIn('"calyx-sv"', pipeline)

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
