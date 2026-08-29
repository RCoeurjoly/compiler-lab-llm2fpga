"""Tests for the independent RTL-width TinyStories-1M LayerNorm primitive."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/tinystories_1m_rtl_layernorm.py"
RECEIPT = ROOT / "artifacts/reference/tinystories-1m-layernorm-semantics.json"
VECTOR = ROOT / "artifacts/reference/tinystories-1m-rtl-layernorm-vector.json"


def load_module():
    spec = importlib.util.spec_from_file_location("rtl_layernorm", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RtlLayerNormTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_declared_port_shape_is_exactly_one_width_64_row(self) -> None:
        """Changing the primitive port shape must make this test fail."""
        with self.assertRaisesRegex(self.module.RtlLayerNormError, "shape_mismatch"):
            self.module.fixed_layer_norm_rtl([0] * 63, [65536] * 63, [0] * 63)

    def test_overflow_witness_matches_authenticated_rtl_width_result(self) -> None:
        """Dropping a declared accumulator width must make this test fail."""
        values = [-2**31, 2**31 - 1] * 32
        result = self.module.fixed_layer_norm_rtl(values, [65536] * 64, [0] * 64, details=True)
        self.assertEqual(result["mean_q16_16"], 0)
        self.assertEqual(result["square_sum_72"], 295147905041913872416)
        self.assertEqual(result["variance_u64"], 4611686016279947206)
        self.assertEqual(result["output_q16_16"][:2], [-65536, 65536])

    def test_affine_assignment_wraps_to_signed_32_bits(self) -> None:
        """Replacing the output assignment with unbounded integers must fail."""
        self.assertEqual(
            self.module.affine_rtl([-370727, 370727], [2**31 - 1, 2**31 - 1], [0, 0]),
            [736919557, -736919558],
        )

    def test_generated_vector_is_bound_to_authenticated_rtl_profile(self) -> None:
        """An input/result substitution must be detected by the vector checksum."""
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        vector = json.loads(VECTOR.read_text(encoding="utf-8"))
        self.assertEqual(vector["profile"], "synthesizable_rtl")
        self.assertEqual(vector["layernorm_receipt_sha256"], receipt["receipt_sha256"])
        self.assertEqual(vector["sha256"], self.module.vector_sha256(vector))
        details = self.module.fixed_layer_norm_rtl(
            vector["input_q16_16"], vector["gamma_q16_16"], vector["beta_q16_16"], details=True
        )
        self.assertEqual(details, vector["result"])

    def test_lowering_reports_backend_boundary_not_missing_compiler_bridge(self) -> None:
        """Regressing to the pre-bridge boundary or claiming equivalence must fail."""
        state = self.module.compiler_integration_status()
        self.assertEqual(state["status"], "unsupported")
        self.assertEqual(state["bridge_status"], "custom_op_emitted")
        self.assertEqual(state["code"], "fixed_layer_norm_backend_lowering_not_implemented")
        self.assertEqual(state["next_unsupported_operation"], "llm2fpga.fixed_layer_norm_q16_16")
        self.assertFalse(state["runtime_equivalent"])
        self.assertFalse(state["board_authenticated"])


if __name__ == "__main__":
    unittest.main()
