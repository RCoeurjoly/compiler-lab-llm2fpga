"""TDD contract for lowering the authenticated fixed-point schema to Calyx."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
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
    def test_generated_sv_observes_exact_requantized_fixture_values(self):
        """Catches software-supplied or arithmetically inexact result memories."""
        lowerer = load_lowerer()
        observed = lowerer.run_requantize_sv(
            lowerer.generate_requantize_kernel(SCHEMA, FIXTURE), FIXTURE
        )
        fixture = json.loads(FIXTURE.read_text())
        flatten = lambda rows: [value for row in rows for value in row]
        self.assertEqual(set(observed), {"codes_i8", "q16_16"})
        self.assertEqual(
            observed["codes_i8"],
            flatten(fixture["tensors"]["requantized_codes_i8"]["values"]),
        )
        self.assertEqual(
            observed["q16_16"],
            flatten(fixture["tensors"]["requantized_q16_16"]["values"]),
        )

    def test_requantize_sv_rejects_post_generation_fixture_mutation(self):
        """Catches a runner that trusts generation-time fixture authority."""
        lowerer = load_lowerer()
        artifact = lowerer.generate_requantize_kernel(SCHEMA, FIXTURE)
        mutated = json.loads(FIXTURE.read_text())
        mutated["tensors"]["gemv_accumulator_i64"]["values"][0][0] += 1
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "mutated-fixture.json"
            fixture_path.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture.*hash|fixture.*authority"):
                lowerer.run_requantize_sv(artifact, fixture_path)

    def test_generated_sv_observes_full_row_major_accumulator_trace(self):
        """Catches a generated-SV kernel that omits a row/output checkpoint."""
        lowerer = load_lowerer()
        observed = lowerer.run_full_gemv_sv(
            lowerer.generate_full_gemv_kernel(SCHEMA, FIXTURE), FIXTURE
        )
        fixture = json.loads(FIXTURE.read_text())
        expected = [
            value
            for row in fixture["tensors"]["gemv_accumulator_i64"]["values"]
            for value in row
        ]
        self.assertEqual(observed["accumulator_trace_i64"], expected)
        self.assertEqual(
            observed["trace_sha256"],
            fixture["tensors"]["gemv_accumulator_i64"]["little_endian_int64_sha256"],
        )

    def test_generated_sv_rejects_post_generation_fixture_mutation(self):
        lowerer = load_lowerer()
        artifact = lowerer.generate_one_output_kernel(SCHEMA, FIXTURE)
        mutated = json.loads(FIXTURE.read_text())
        mutated["tensors"]["activation_codes_i8"]["values"][0][0] += 1
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "mutated-fixture.json"
            fixture_path.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture.*hash|fixture.*authority"):
                lowerer.run_generated_sv(artifact, fixture_path, row=0, output=0)

    def test_generated_sv_observes_first_64_mac_accumulator(self):
        lowerer = load_lowerer()
        artifact = lowerer.generate_one_output_kernel(SCHEMA, FIXTURE)
        observed = lowerer.run_generated_sv(artifact, FIXTURE, row=0, output=0)
        expected = json.loads(FIXTURE.read_text())[
            "tensors"
        ]["gemv_accumulator_i64"]["values"][0][0]
        self.assertEqual(observed["accumulator_i64"], expected)
        self.assertGreater(observed["cycles"], 64)

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

    def test_observed_trace_rejects_altered_signed_datapath(self):
        lowerer = load_lowerer()
        artifact = lowerer.lower_schema(SCHEMA, FIXTURE)
        observed = lowerer.observed_value_trace(artifact, FIXTURE)
        self.assertEqual(observed, lowerer.ordered_value_trace(artifact, FIXTURE))
        altered = type(artifact)(
            artifact.futil.replace("std_smult_pipe", "std_mult_pipe", 1), artifact.provenance
        )
        with self.assertRaisesRegex(ValueError, "signed datapath"):
            lowerer.observed_value_trace(altered, FIXTURE)

    def test_altered_rounding_rule_is_rejected_before_lowering(self):
        lowerer = load_lowerer()
        for field, value in (
            ("rounding", "toward_zero"),
            ("signedness", "unsigned"),
            ("saturation", [-127, 127]),
            ("width", 16),
        ):
            with self.subTest(field=field):
                altered = json.loads(SCHEMA.read_text())
                altered["requantize"][field] = value
                with tempfile.TemporaryDirectory() as directory:
                    schema_path = Path(directory) / "altered-schema.json"
                    schema_path.write_text(json.dumps(altered), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "requantize|rounding"):
                        lowerer.generate_requantize_kernel(schema_path, FIXTURE)


if __name__ == "__main__":
    unittest.main()
