"""TDD contract for lowering the authenticated fixed-point schema to Calyx."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOWERER = ROOT / "scripts/pipeline/lower_fixed_point_schema_to_calyx.py"
SCHEMA = ROOT / "artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-schema.json"
FIXTURE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json"


def load_lowerer():
    spec = importlib.util.spec_from_file_location("fixed_point_schema_calyx", LOWERER)
    assert spec and spec.loader, "Task 3 Calyx lowerer is missing"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FixedPointSchemaCalyxTest(unittest.TestCase):
    def test_schema_lowers_to_explicit_memories_and_ordered_fixture_trace(self):
        lowerer = load_lowerer()
        artifact = lowerer.lower_schema(SCHEMA, FIXTURE)
        self.assertIn("mem_d1", artifact.futil)
        self.assertIn("group load_activation", artifact.futil)
        self.assertIn("group gemv_step", artifact.futil)
        self.assertIn("group requantize", artifact.futil)
        self.assertNotIn("scf.", artifact.futil)
        self.assertNotIn("TinyStories/rtl", artifact.futil)
        trace = lowerer.ordered_value_trace(artifact, FIXTURE)
        fixture = json.loads(FIXTURE.read_text())
        flatten = lambda rows: [value for row in rows for value in row]
        self.assertEqual(len(trace["gemv"]), 4 * 64)
        self.assertEqual(trace["gemv"][-1]["accumulator_i64"], flatten(fixture["tensors"]["gemv_accumulator_i64"]["values"])[-1])
        self.assertEqual(trace["requantized_codes_i8"], flatten(fixture["tensors"]["requantized_codes_i8"]["values"]))
        self.assertEqual(trace["requantized_q16_16"], flatten(fixture["tensors"]["requantized_q16_16"]["values"]))

    def test_altered_rounding_rule_is_rejected_before_lowering(self):
        lowerer = load_lowerer()
        altered = json.loads(SCHEMA.read_text())
        altered["requantize"]["rounding"] = "toward_zero"
        with self.assertRaisesRegex(ValueError, "requantize|rounding"):
            lowerer.lower_schema_receipt(altered, FIXTURE)


if __name__ == "__main__":
    unittest.main()
