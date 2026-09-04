from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "tools/fixed_point_schema/fixed_point_schema.py"
FIXTURE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json"


def load_plugin():
    spec = importlib.util.spec_from_file_location("fixed_point_schema", PLUGIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedPointSchemaTest(unittest.TestCase):
    def test_schema_has_logical_ssa_and_exact_requantize_attributes(self):
        plugin = load_plugin()
        schema = plugin.build_schema(FIXTURE)
        self.assertIn('"fixed.gemv"', schema["mlir"])
        self.assertIn('"fixed.requantize"', schema["mlir"])
        plugin.verify_schema(schema, FIXTURE)

    def test_missing_or_altered_requantize_attribute_is_rejected(self):
        plugin = load_plugin()
        schema = plugin.build_schema(FIXTURE)
        for key, value in (("rounding", "toward_zero"), ("signedness", "unsigned"), ("saturation", [-127, 127]), ("width", 16), ("scale", "missing")):
            altered = {**schema, "requantize": {**schema["requantize"], key: value}}
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "requantize"):
                    plugin.verify_schema(altered, FIXTURE)

    def test_schema_evaluation_hashes_equal_fixture(self):
        plugin = load_plugin()
        schema = plugin.build_schema(FIXTURE)
        self.assertEqual(plugin.evaluate_schema(schema, FIXTURE), plugin.fixture_output_hashes(FIXTURE))

    def test_forged_mlir_attribute_and_operand_are_rejected(self):
        plugin = load_plugin()
        schema = plugin.build_schema(FIXTURE)
        for old, new in (("nearest_ties_away_from_zero", "toward_zero"), ("%acc, %output_scale", "%acc, %input_scale")):
            forged = {**schema, "mlir": schema["mlir"].replace(old, new, 1)}
            with self.subTest(old=old):
                with self.assertRaisesRegex(ValueError, "requantize|self-hash|scale operand"):
                    plugin.verify_schema(forged, FIXTURE)

    def test_wrong_incoming_mlir_is_rejected(self):
        plugin = load_plugin()
        with self.assertRaisesRegex(ValueError, "incoming MLIR"):
            plugin.build_schema(FIXTURE, "module { %x = \"arith.constant\"() : () -> i64 }")

    def test_substituted_fixture_producer_and_wrong_fixture_operand_are_rejected(self):
        plugin = load_plugin()
        schema = plugin.build_schema(FIXTURE)
        forged_producer = {**schema, "mlir": schema["mlir"].replace('tensor = "output_scale_q8_24"', 'tensor = "weight_scale_q8_24"', 1)}
        forged_operand = {**schema, "mlir": schema["mlir"].replace('%acc, %output_scale', '%acc, %weight_scale', 1)}
        for forged in (forged_producer, forged_operand):
            # An attacker can recompute the outer receipt hash.  The verifier
            # must still reject the structural SSA/provenance substitution.
            forged["receipt_sha256"] = plugin.canonical(
                {key: value for key, value in forged.items() if key != "receipt_sha256"}
            )
            with self.assertRaisesRegex(ValueError, "producer|operand|fixture"):
                plugin.verify_schema(forged, FIXTURE)


if __name__ == "__main__":
    unittest.main()
