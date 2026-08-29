"""Tests for the authenticated fixed LayerNorm backend legalization."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/lower_tinystories_1m_fixed_layernorm_backend.py"
BRIDGE = ROOT / "artifacts/comparison/tinystories-1m-fixed-layernorm-bridge.json"
BRIDGE_MLIR = ROOT / "artifacts/comparison/tinystories-1m-fixed-layernorm-bridge.mlir"
VECTOR = ROOT / "artifacts/reference/tinystories-1m-rtl-layernorm-vector.json"


def load_module():
    spec = importlib.util.spec_from_file_location("fixed_layernorm_backend", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedLayerNormBackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.bundle = cls.module.load_authenticated_inputs(BRIDGE, BRIDGE_MLIR, VECTOR)

    def test_authenticated_task3p_receipt_is_required(self) -> None:
        self.assertEqual(self.bundle["descriptor"]["op"], "llm2fpga.fixed_layer_norm_q16_16")
        forged = json.loads(BRIDGE.read_text(encoding="utf-8"))
        forged["custom_op"]["attributes"]["variance_sum_width"] = 64
        forged["custom_op"]["sha256"] = self.module.canonical_sha256(
            {key: value for key, value in forged["custom_op"].items() if key != "sha256"}
        )
        forged["sha256"] = self.module.canonical_sha256(
            {key: value for key, value in forged.items() if key != "sha256"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "forged.json"
            path.write_text(json.dumps(forged, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(self.module.BackendLoweringError, "bridge_artifact_identity_mismatch"):
                self.module.load_authenticated_inputs(path, BRIDGE_MLIR, VECTOR)

    def test_renderer_eliminates_custom_op_and_preserves_four_tensor_memories(self) -> None:
        mlir = self.module.render_flat_scf(self.bundle)
        self.assertNotIn("llm2fpga.fixed_layer_norm_q16_16", mlir)
        self.assertNotIn("tensor<", mlir)
        self.assertNotRegex(mlir, r"i(?:6[5-9]|7[0-9])\b")
        self.assertIn("func.func @main(%input: memref<64xi32>, %gamma: memref<64xi32>, %beta: memref<64xi32>, %output: memref<64xi32>)", mlir)
        self.assertEqual(mlir.count("memref.alloc"), 0)
        self.assertIn(self.bundle["bridge_file_sha256"], mlir)
        self.assertIn(self.bundle["descriptor"]["sha256"], mlir)
        for digest in self.bundle["checkpoint_identities"].values():
            self.assertIn(digest, mlir)

    def test_limb_algorithm_matches_all_recorded_layernorm_fields(self) -> None:
        trace = self.module.execute_lowered_algorithm(self.bundle["vector"])
        self.assertEqual(trace, self.bundle["vector"]["result"])
        self.assertEqual(trace["square_sum_72"], 274877906944)
        self.assertEqual(trace["deviation_floor_sqrt"], 65536)

    def test_report_is_honest_before_backend_execution(self) -> None:
        mlir = self.module.render_flat_scf(self.bundle)
        report = self.module.make_report(
            self.bundle,
            mlir,
            calyx_mlir=None,
            calyx_command=None,
            calyx_diagnostic="backend conversion not run",
        )
        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["backend_ir"]["status"], "flat_scf_emitted")
        self.assertEqual(report["numeric_trace"]["status"], "algorithm_matched_backend_execution_not_run")
        self.assertEqual(report["first_unsupported_operation"]["code"], "calyx_backend_execution_not_verified")
        self.assertIsNone(report["compiler_artifacts"]["systemverilog"])
        self.assertIsNone(report["compiler_artifacts"]["rtlil"])
        self.assertFalse(report["provenance"]["reference_source_or_rtl_copied"])

    def test_report_accepts_only_exact_calyx_conversion_output(self) -> None:
        mlir = self.module.render_flat_scf(self.bundle)
        calyx = "module attributes {calyx.entrypoint = \"main\"} {\n  calyx.component @main() {}\n}\n"
        report = self.module.make_report(
            self.bundle,
            mlir,
            calyx_mlir=calyx,
            calyx_command=["circt-opt", "--lower-scf-to-calyx=top-level-function=main"],
            calyx_diagnostic="",
        )
        self.assertEqual(report["backend_ir"]["status"], "calyx_emitted_not_executed")
        self.assertEqual(report["compiler_artifacts"]["calyx"]["sha256"], self.module.sha256_bytes(calyx.encode()))


if __name__ == "__main__":
    unittest.main()
