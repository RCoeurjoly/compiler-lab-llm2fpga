import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class FullTinyStoriesW8A8ScoutTest(unittest.TestCase):
    def test_pt2e_zero_point_legalization_has_positive_and_negative_reproducers(self) -> None:
        reproducer = REPO_ROOT / "reproducers" / "pt2e-tosa-zero-point"
        positive = (reproducer / "input.mlir").read_text(encoding="utf-8")
        negative = (reproducer / "unrelated-add.mlir").read_text(encoding="utf-8")

        self.assertIn("tosa.cast %arg0", positive)
        self.assertIn("dense<26>", positive)
        self.assertIn("tosa.add %rounded_i8, %zero_point", positive)
        self.assertIn("tosa.cast %quantized_i8", positive)
        self.assertIn("tosa.add %lhs, %rhs", negative)
        self.assertNotIn("tosa.const", negative)

    def test_mlir_plugin_registers_pt2e_zero_point_legalization(self) -> None:
        source = (
            REPO_ROOT / "tools" / "mlir-passes" / "LegalizePt2eTosaZeroPoint.cpp"
        ).read_text(encoding="utf-8")
        cmake = (
            REPO_ROOT / "tools" / "mlir-passes" / "CMakeLists.txt"
        ).read_text(encoding="utf-8")
        plugin = (
            REPO_ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("llm2fpga-legalize-pt2e-tosa-zero-point", source)
        self.assertIn("tosa::AddOp", source)
        self.assertIn("tosa::RescaleOp", source)
        self.assertIn("registerLegalizePt2eTosaZeroPointPass", source)
        self.assertIn("LegalizePt2eTosaZeroPoint.cpp", cmake)
        self.assertIn("MLIRTosaDialect", cmake)
        self.assertIn("registerLegalizePt2eTosaZeroPointPass", plugin)

    def test_pt2e_zero_point_match_does_not_depend_on_consumers(self) -> None:
        source = (
            REPO_ROOT / "tools" / "mlir-passes" / "LegalizePt2eTosaZeroPoint.cpp"
        ).read_text(encoding="utf-8")

        self.assertNotIn("hasOneUse", source)
        self.assertNotIn("user_begin", source)
        self.assertNotIn("wideningCast", source)

    def test_tosa_pipeline_uses_plugin_built_for_torch_mlir_abi(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("llm2fpgaTorchMlirPasses =", flake)
        self.assertIn("mlir = mlirForTorchMlir", flake)
        self.assertIn("llvmPackages = torchMlirLlvmPackages", flake)
        tosa_pipeline = re.search(
            r"pipelineLibTosa = import ./nix/pipeline.nix \{.*?^        \};",
            flake,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(tosa_pipeline)
        self.assertIn(
            "mlirPasses = llm2fpgaTorchMlirPasses", tosa_pipeline.group(0)
        )

    def test_full_model_w8a8_is_registered_with_existing_pt2e_adapter(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")

        match = re.search(
            r'"tinystories-w8a8" = registerModel \{.*?^  \};',
            models,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        block = match.group(0)

        self.assertIn('quantization = "pt2e-static-w8a8"', block)
        self.assertIn("model_adapter_pt2e_static_quant.py", block)
        self.assertIn("hfSnapshot = tinyStories1m.snapshot", block)
        self.assertIn("pythonWithTinyStoriesTorchAO", block)

    def test_full_model_w8a8_has_public_tosa_no_handshake_alias(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        match = re.search(
            r'alias = "tinystories-w8a8-via-tosa-no-handshake";.*?^          \}',
            flake,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        block = match.group(0)

        self.assertIn('model = "tinystories-w8a8"', block)
        self.assertIn("packages = pipelineStagePackagesTosaNoHandshake", block)
        self.assertIn("stages = noHandshakeStages", block)

    def test_graph_shape_audit_reports_qdq_wrapped_float_matmul(self) -> None:
        script = REPO_ROOT / "scripts" / "pipeline" / "pt2e_graph_shape_audit.py"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            graph = tmp_path / "graph.txt"
            json_out = tmp_path / "report.json"
            markdown_out = tmp_path / "report.md"
            graph.write_text(
                """
                %0 = torch.ops.quantized_decomposed.dequantize_per_tensor.default(%q)
                %1 = torch.ops.aten.matmul.default(%0, %weight)
                """,
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--graph",
                    str(graph),
                    "--json-out",
                    str(json_out),
                    "--markdown-out",
                    str(markdown_out),
                    "--model-label",
                    "synthetic-w8a8",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "fail")
            self.assertIn("float_matmul_after_dequant", report["failure_reasons"])
            self.assertEqual(report["op_counts"]["aten.matmul"], 1)
            self.assertIn("PT2E Graph Shape Audit", markdown_out.read_text(encoding="utf-8"))

    def test_graph_shape_audit_is_exposed_as_non_gating_package(self) -> None:
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn('"tinystories-w8a8-pt2e-graph-shape-audit"', flake)
        self.assertIn('pipelineStagePackages."tinystories-w8a8-pytorch-exported"', flake)
        self.assertIn("pt2e_graph_shape_audit.py", flake)
        self.assertNotIn(
            "pt2e_graph_shape_audit.py \\\n+              --fail-on-nonstructural",
            flake,
        )


if __name__ == "__main__":
    unittest.main()
