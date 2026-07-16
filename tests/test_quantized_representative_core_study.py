import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY_INPUT = REPO_ROOT / "TinyStories" / "quantized_rc_study_input.json"
STUDY_INPUT_MODULE = REPO_ROOT / "TinyStories" / "quantized_rc_study_input.py"
STUDY_FULL_ADAPTER = REPO_ROOT / "TinyStories" / "model_adapter_pt2e_w8a8_study.py"
STUDY_RC_ADAPTER = (
    REPO_ROOT
    / "TinyStories"
    / "model_adapter_quantized_representative_core_pt2e_w8a8.py"
)
METRICS_WRITER = (
    REPO_ROOT / "scripts" / "pipeline" / "write_torch_mlir_study_metrics.py"
)
COMPILE_PYTORCH = REPO_ROOT / "scripts" / "compile-pytorch.py"
STUDY_ADR = REPO_ROOT / "docs" / "adr" / "2026-07-16-quantized-representative-core-study.md"
STUDY_RESULT = (
    REPO_ROOT
    / "docs"
    / "results"
    / "2026-07-16-quantized-representative-core-pt2e-w8a8.md"
)
STUDY_ARTIFACT = (
    REPO_ROOT
    / "artifacts"
    / "quantized-representative-core-pt2e-w8a8"
    / "result.json"
)


def load_study_input_module():
    spec = importlib.util.spec_from_file_location(
        "quantized_rc_study_input", STUDY_INPUT_MODULE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {STUDY_INPUT_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuantizedRepresentativeCoreStudyTest(unittest.TestCase):
    def test_structural_input_has_eight_positions_and_a_repeat(self) -> None:
        self.assertTrue(STUDY_INPUT.exists())
        payload = json.loads(STUDY_INPUT.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["context_length"], 8)
        self.assertEqual(len(payload["full_token_ids"]), 8)
        self.assertEqual(payload["full_token_ids"][1], payload["full_token_ids"][4])
        self.assertEqual(payload["purpose"], "structural-pt2e-calibration")

    def test_reduced_vocab_mapping_preserves_equality_and_order(self) -> None:
        self.assertTrue(STUDY_INPUT_MODULE.exists())
        study_input = load_study_input_module()

        mapped = study_input.map_full_token_ids_to_reduced_vocab(
            (100, 200, 100, 300, 200, 400), vocab_size=4
        )

        self.assertEqual(mapped, (0, 1, 0, 2, 1, 3))
        with self.assertRaisesRegex(ValueError, "vocabulary"):
            study_input.map_full_token_ids_to_reduced_vocab(
                (100, 200, 300), vocab_size=2
            )

    def test_clean_rc_adapter_has_no_hardware_semantic_substitutions(self) -> None:
        self.assertTrue(STUDY_RC_ADAPTER.exists())
        source = STUDY_RC_ADAPTER.read_text(encoding="utf-8")

        for forbidden in (
            "Int8Embedding",
            "FixedPointLayerNormBridge",
            "QuadraticGeluHardwareApproximation",
            "replace_attention_with_hardware_friendly_attention",
            "replace_layernorm_with_fixed_point_bridge",
            "replace_gelu_with_quadratic_hardware_activation",
        ):
            self.assertNotIn(forbidden, source)

        self.assertIn("AutoModelForCausalLM.from_config", source)
        self.assertIn("attention_types_for_layers", source)
        self.assertIn("study_example_inputs(vocab_size", source)

    def test_study_adapters_use_static_eight_token_inputs(self) -> None:
        self.assertTrue(STUDY_FULL_ADAPTER.exists())
        self.assertTrue(STUDY_RC_ADAPTER.exists())

        full_source = STUDY_FULL_ADAPTER.read_text(encoding="utf-8")
        rc_source = STUDY_RC_ADAPTER.read_text(encoding="utf-8")
        self.assertIn("study_example_inputs", full_source)
        self.assertIn("study_example_inputs", rc_source)
        self.assertIn("export_pt2e_w8a8", full_source)
        self.assertIn("export_pt2e_w8a8", rc_source)

    def test_metrics_writer_records_duration_and_mlir_identity(self) -> None:
        self.assertTrue(METRICS_WRITER.exists())
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mlir = tmp_path / "model.torch.mlir"
            metrics = tmp_path / "metrics.json"
            phase_timing = tmp_path / "phase-timing.json"
            mlir.write_text("module {}\n", encoding="utf-8")
            phase_timing.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "torch_export_load_elapsed_ns": 10,
                        "torch_mlir_import_elapsed_ns": 20,
                        "mlir_text_render_elapsed_ns": 30,
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(METRICS_WRITER),
                    "--mlir",
                    str(mlir),
                    "--elapsed-ns",
                    "123456",
                    "--phase-timing",
                    str(phase_timing),
                    "--out",
                    str(metrics),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(metrics.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["lowering_elapsed_ns"], 123456)
            self.assertEqual(payload["mlir_bytes"], len("module {}\n"))
            self.assertEqual(len(payload["mlir_sha256"]), 64)
            self.assertEqual(payload["torch_mlir_import_elapsed_ns"], 20)

    def test_torch_mlir_compiler_exposes_phase_timing_without_changing_default_output(self) -> None:
        source = COMPILE_PYTORCH.read_text(encoding="utf-8")

        self.assertIn('"--timing-json"', source)
        self.assertIn("torch_export_load_elapsed_ns", source)
        self.assertIn("torch_mlir_import_elapsed_ns", source)

    def test_nix_exposes_pt2e_rc_study_without_fpga_utilization_claim(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn('"tinystories-w8a8-rc-study-full"', models)
        self.assertIn(
            "model_adapter_quantized_representative_core_pt2e_w8a8.py", models
        )
        self.assertIn("TINYSTORIES_RC_STUDY_CONTEXT_LENGTH=8", models)
        for candidate in (
            "tinystories-w8a8-rc-study-mask9",
            "tinystories-w8a8-rc-study-mask9-vocab6",
            "tinystories-w8a8-rc-study-mask9-vocab6-width1",
            "tinystories-w8a8-rc-study-mask9-vocab6-width2",
            "tinystories-w8a8-rc-study-mask9-vocab6-width3",
            "tinystories-w8a8-rc-study-mask9-vocab6-width2-window1",
            "tinystories-w8a8-rc-study-minimum",
        ):
            self.assertIn(f'"{candidate}"', models)
        self.assertIn('"tinystories-w8a8-rc-study"', flake)
        self.assertIn("qualify_quantized_representative_core.py", flake)
        self.assertNotIn("rc-study-xc7", flake)

    def test_study_docs_distinguish_structural_finalist_from_iteration_surrogate(self) -> None:
        self.assertTrue(STUDY_ADR.exists())
        self.assertTrue(STUDY_RESULT.exists())

        adr = STUDY_ADR.read_text(encoding="utf-8")
        result = STUDY_RESULT.read_text(encoding="utf-8")
        self.assertIn("structural finalist", adr.lower())
        self.assertIn("iteration surrogate", adr.lower())
        self.assertIn("mask9-vocab6-width2", result)
        self.assertIn("not an FPGA resource or equivalence result", result)

    def test_study_artifact_records_the_negative_speed_result(self) -> None:
        self.assertTrue(STUDY_ARTIFACT.exists())
        payload = json.loads(STUDY_ARTIFACT.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["status"], "coverage-valid-finalist-without-speed-eligibility"
        )
        self.assertIsNone(payload["selected_candidate"])
        self.assertEqual(
            payload["structural_finalist"]["key"], "mask9-vocab6-width2"
        )
        self.assertTrue(payload["structural_finalist"]["coverage_complete"])
        self.assertLess(
            payload["structural_finalist"]["lowering_speedup"],
            payload["thresholds"]["minimum_lowering_speedup"],
        )


if __name__ == "__main__":
    unittest.main()
