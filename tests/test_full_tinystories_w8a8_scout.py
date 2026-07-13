import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class FullTinyStoriesW8A8ScoutTest(unittest.TestCase):
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
