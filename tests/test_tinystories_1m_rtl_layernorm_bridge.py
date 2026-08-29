"""Tests for the authenticated fixed-width LayerNorm compiler bridge."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/bridge_tinystories_1m_rtl_layernorm.py"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-layernorm-semantics.json"
VECTOR = ROOT / "artifacts/reference/tinystories-1m-rtl-layernorm-vector.json"
PRIMITIVE = ROOT / "scripts/comparison/tinystories_1m_rtl_layernorm.py"
QDQ_PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
CANONICAL_EXPORT = Path("/tmp/task3l-fixed-qdq-lowering/exported.pt2")
CANONICAL_ADAPTER_RECEIPT = Path("/tmp/task3l-fixed-qdq-lowering/adapter-receipt.json")


def load_module():
    spec = importlib.util.spec_from_file_location("rtl_layernorm_bridge", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RtlLayerNormBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.evidence = cls.module.load_evidence(PROFILE, VECTOR, PRIMITIVE, QDQ_PROFILE)

    def source_op(self, **updates):
        value = {
            "graph_index": 149,
            "name": "layer_norm",
            "target": "aten.layer_norm.default",
            "input_shape": [1, 4, 64],
            "input_dtype": "torch.float32",
            "normalized_shape": [64],
            "weight_shape": [64],
            "weight_dtype": "torch.float32",
            "weight_parameter": "model.transformer.h.0.ln_1.weight",
            "bias_shape": [64],
            "bias_dtype": "torch.float32",
            "bias_parameter": "model.transformer.h.0.ln_1.bias",
            "epsilon": 1e-5,
            "cudnn_enable": True,
        }
        value.update(updates)
        return value

    def test_evidence_authenticates_profile_vector_primitive_and_twelve_checkpoints(self) -> None:
        self.assertEqual(self.evidence["profile"], "synthesizable_rtl")
        self.assertEqual(self.evidence["width"], 64)
        self.assertEqual(self.evidence["format"], "signed_q16.16_int32")
        self.assertEqual(len(self.evidence["checkpoint_identities"]), 12)
        self.assertEqual(
            list(self.evidence["checkpoint_identities"]),
            list(self.module.CHECKPOINT_SHAPES),
        )
        self.assertEqual(self.evidence["numeric_trace"]["status"], "matched")
        self.assertEqual(
            self.evidence["numeric_trace"]["software_result_sha256"],
            self.evidence["numeric_trace"]["bridge_result_sha256"],
        )

    def test_bridge_emits_deterministic_custom_op_and_mlir_lowering_hook(self) -> None:
        descriptor = self.module.bridge_source_op(self.source_op(), self.evidence, token_index=3)
        self.assertEqual(descriptor["op"], "llm2fpga.fixed_layer_norm_q16_16")
        self.assertEqual(descriptor["operand_types"], ["tensor<64xi32>"] * 3)
        self.assertEqual(descriptor["result_types"], ["tensor<64xi32>"])
        self.assertEqual(descriptor["attributes"]["epsilon_q32"], 42950)
        self.assertEqual(descriptor["attributes"]["mean_accumulator_width"], 64)
        self.assertEqual(descriptor["attributes"]["variance_sum_width"], 72)
        self.assertEqual(descriptor["attributes"]["token_index"], 3)

        first = self.module.lower_custom_op_to_mlir(descriptor)
        second = self.module.lower_custom_op_to_mlir(copy.deepcopy(descriptor))
        self.assertEqual(first, second)
        self.assertIn('"llm2fpga.fixed_layer_norm_q16_16"', first)
        self.assertIn("tensor<64xi32>", first)
        self.assertIn("}> :", first)
        self.assertNotIn("}}>", first)
        self.assertNotIn("gptneo_layernorm", first)

    def test_bridge_fails_closed_on_dimension_dtype_and_parameter_changes(self) -> None:
        cases = [
            ("unsupported_source_shape", {"input_shape": [1, 5, 64]}),
            ("unsupported_normalized_shape", {"normalized_shape": [32]}),
            ("unsupported_source_dtype", {"input_dtype": "torch.float16"}),
            ("unsupported_parameter_shape", {"weight_shape": [32]}),
            ("unsupported_parameter_dtype", {"bias_dtype": "torch.float64"}),
            ("unsupported_epsilon", {"epsilon": 1e-6}),
            ("unsupported_layernorm_parameter", {"cudnn_enable": False}),
            ("parameter_binding_mismatch", {"weight_parameter": "model.transformer.h.1.ln_1.weight"}),
        ]
        for code, update in cases:
            with self.subTest(code=code), self.assertRaisesRegex(self.module.LayerNormBridgeError, code):
                self.module.bridge_source_op(self.source_op(**update), self.evidence, token_index=3)

    def test_tampered_task3o_vector_fails_even_when_self_rehashed(self) -> None:
        vector = json.loads(VECTOR.read_text(encoding="utf-8"))
        vector["input_q16_16"][0] += 1
        vector["sha256"] = self.module.canonical_sha256(
            {key: value for key, value in vector.items() if key != "sha256"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "vector.json"
            candidate.write_text(json.dumps(vector, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(self.module.LayerNormBridgeError, "layernorm_vector_identity_mismatch"):
                self.module.load_evidence(PROFILE, candidate, PRIMITIVE, QDQ_PROFILE)

    def test_report_moves_boundary_to_backend_legalization_without_rtl_claim(self) -> None:
        descriptor = self.module.bridge_source_op(self.source_op(), self.evidence, token_index=3)
        mlir = self.module.lower_custom_op_to_mlir(descriptor)
        report = self.module.make_report(
            source_op=self.source_op(), descriptor=descriptor, mlir=mlir, evidence=self.evidence
        )
        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["bridge_status"], "custom_op_emitted")
        self.assertEqual(
            report["first_unsupported_operation"]["code"],
            "fixed_layer_norm_backend_lowering_not_implemented",
        )
        self.assertEqual(
            report["first_unsupported_operation"]["target"],
            "llm2fpga.fixed_layer_norm_q16_16",
        )
        self.assertEqual(report["compiler_artifacts"]["systemverilog"], None)
        self.assertEqual(report["compiler_artifacts"]["rtlil"], None)
        self.assertFalse(report["provenance"]["reference_source_or_rtl_copied"])
        self.assertFalse(report["board_authenticated"])

    @unittest.skipUnless(
        CANONICAL_EXPORT.is_file() and CANONICAL_ADAPTER_RECEIPT.is_file(),
        "canonical Task 3l package export is unavailable",
    )
    def test_canonical_package_export_reaches_exact_bridge(self) -> None:
        source_op = self.module.inspect_exported_layernorm(
            CANONICAL_EXPORT, CANONICAL_ADAPTER_RECEIPT, graph_index=149
        )
        descriptor = self.module.bridge_source_op(source_op, self.evidence, token_index=3)
        self.assertEqual(source_op["target"], "aten.layer_norm.default")
        self.assertEqual(source_op["weight_parameter"], "model.transformer.h.0.ln_1.weight")
        self.assertEqual(descriptor["source"]["exported_program_sha256"], self.module.EXPORTED_PROGRAM_SHA256)


if __name__ == "__main__":
    unittest.main()
