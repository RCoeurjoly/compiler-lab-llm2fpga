from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
CAPTURE = ROOT / "TinyStories/capture_fixed_point_mlp_crossing_slice.py"
LOWERER = ROOT / "scripts/pipeline/lower_fixed_point_mlp_crossing_to_calyx.py"
RUNNER = ROOT / "scripts/pipeline/run_fixed_point_mlp_crossing_sv.py"
SV_RECEIPT = ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-sv-receipt.json"

EXPECTED_SHAPES = {
    "c_fc_input_codes_i8": [4, 64],
    "c_fc_input_scale_q8_24": [64],
    "c_fc_input_q16_16": [4, 64],
    "c_fc_accumulator_i64": [4, 256],
    "c_fc_post_weight_rescale_bias_q16_16": [4, 256],
    "c_fc_output_codes_i8": [4, 256],
    "c_fc_output_scale_q8_24": [256],
    "c_fc_output_q16_16": [4, 256],
    "gelu_input_q16_16": [4, 256],
    "gelu_output_q16_16": [4, 256],
    "gelu_lut_q12": [8192],
    "c_proj_input_codes_i8": [4, 256],
    "c_proj_input_scale_q8_24": [256],
    "c_proj_input_q16_16": [4, 256],
    "c_proj_accumulator_i64": [4, 64],
    "c_proj_post_weight_rescale_bias_q16_16": [4, 64],
    "c_proj_output_codes_i8": [4, 64],
    "c_proj_output_scale_q8_24": [64],
    "c_proj_output_q16_16": [4, 64],
    "c_fc_weight_codes_i8": [256, 64],
    "c_fc_weight_scale_q8_24": [256],
    "c_fc_bias_q16_16": [256],
    "c_proj_weight_codes_i8": [64, 256],
    "c_proj_weight_scale_q8_24": [64],
    "c_proj_bias_q16_16": [64],
}


def load_capture():
    if not CAPTURE.is_file():
        raise AssertionError("missing authenticated MLP capture module")
    spec = importlib.util.spec_from_file_location("fixed_point_mlp_crossing_capture", CAPTURE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_lowerer():
    if not LOWERER.is_file():
        raise AssertionError("missing fixed-point MLP crossing Calyx lowerer")
    spec = importlib.util.spec_from_file_location(
        "fixed_point_mlp_crossing_calyx", LOWERER
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "fixed_point_mlp_crossing_runner", RUNNER
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def tensor_values(name: str) -> list[int]:
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["tensors"][name][
        "values"
    ]
    return [value for row in rows for value in row]


def canonical(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class FixedPointMlpCrossingTest(unittest.TestCase):
    def test_yosys_066_stat_format_reports_generated_main(self):
        """Catches rejection of Yosys 0.66's count-first stat format."""
        stat = """=== main ===
=== design hierarchy ===
        24 memories
   1282048 memory bits
       2812 cells
"""
        self.assertEqual(
            load_runner()._validate_yosys_stat(stat),
            {"cells": 2812, "memories": 24, "memory_bits": 1282048},
        )

    def test_one_generated_sv_main_matches_every_mlp_checkpoint(self):
        """Catches host-staged or arithmetically inexact MLP composition."""
        lowerer = load_lowerer()
        receipt = lowerer.run_composed_mlp_sv(FIXTURE)
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

        self.assertEqual(receipt["schema"], "tinystories-1m-fixed-point-mlp-crossing-generated-sv-v1")
        self.assertEqual(receipt["fixture_receipt_sha256"], fixture["receipt_sha256"])
        self.assertEqual(receipt["schema_authority"]["schema"], fixture["schema"])
        schema_unsigned = {
            key: value
            for key, value in receipt["schema_authority"].items()
            if key != "receipt_sha256"
        }
        self.assertEqual(
            receipt["schema_authority"]["receipt_sha256"],
            canonical(schema_unsigned),
        )
        self.assertEqual(receipt["execution"]["component_count"], 1)
        self.assertEqual(receipt["execution"]["simulator_runs"], 1)
        self.assertFalse(receipt["execution"]["host_intermediate"])

        checkpoint_tensors = [
            "c_fc_input_q16_16",
            "c_fc_accumulator_i64",
            "c_fc_post_weight_rescale_bias_q16_16",
            "c_fc_output_codes_i8",
            "c_fc_output_q16_16",
            "gelu_output_q16_16",
            "c_proj_input_codes_i8",
            "c_proj_input_q16_16",
            "c_proj_accumulator_i64",
            "c_proj_post_weight_rescale_bias_q16_16",
            "c_proj_output_codes_i8",
            "c_proj_output_q16_16",
        ]
        self.assertEqual(set(receipt["observed"]), set(checkpoint_tensors))
        for name in checkpoint_tensors:
            self.assertEqual(
                receipt["observed"][name]["little_endian_int64_sha256"],
                fixture["tensors"][name]["little_endian_int64_sha256"],
                name,
            )
            self.assertEqual(
                receipt["observed"][name]["count"],
                fixture["tensors"][name]["bytes"] // 8,
                name,
            )

        unsigned = {
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }
        self.assertEqual(receipt["receipt_sha256"], canonical(unsigned))
        self.assertGreater(receipt["execution"]["cycles"], 131072)
        self.assertEqual(
            receipt["calyx_compile_policy"]["disabled_passes"], ["cell-share"]
        )
        self.assertEqual(
            set(receipt["generated_artifacts"]),
            {"futil", "sv", "synthesis_sv", "harness"},
        )
        self.assertTrue(SV_RECEIPT.is_file(), "missing generated-SV MLP receipt")
        committed_receipt = json.loads(SV_RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(committed_receipt, receipt)

    def test_generated_sv_observes_exact_fixed_gelu(self):
        """Catches inexact GELU arithmetic or an omitted hardware checkpoint."""
        lowerer = load_lowerer()
        artifact = lowerer.generate_gelu_kernel(FIXTURE)
        observed = lowerer.run_gelu_sv(artifact, FIXTURE)
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(observed["gelu_q16_16"], tensor_values("gelu_output_q16_16"))
        self.assertEqual(
            observed["little_endian_int64_sha256"],
            fixture["tensors"]["gelu_output_q16_16"][
                "little_endian_int64_sha256"
            ],
        )
        self.assertEqual(
            artifact.provenance["host_preload_memories"],
            ["gelu_input_q16_16", "gelu_lut_q12"],
        )
        self.assertEqual(
            artifact.provenance["calyx_disabled_passes"], ["cell-share"]
        )
        harness = Path(
            artifact.provenance["generated_sv_artifacts"]["harness"]
        ).read_text(encoding="utf-8")
        preload_arrays = [
            line
            for line in harness.splitlines()
            if line.startswith("static const std::int64_t k")
        ]
        self.assertEqual(len(preload_arrays), 2)
        self.assertTrue(any("kGeluInput[1024]" in line for line in preload_arrays))
        self.assertTrue(any("kGeluLut[8192]" in line for line in preload_arrays))
        self.assertNotIn("kExpected", harness)
        self.assertNotIn("kGeluOutput", harness)
        self.assertNotIn("c_fc", artifact.futil)
        self.assertNotIn("c_proj", artifact.futil)

    def test_gelu_sv_rejects_post_generation_fixture_mutation(self):
        """Catches a runner that trusts only generation-time fixture authority."""
        lowerer = load_lowerer()
        artifact = lowerer.generate_gelu_kernel(FIXTURE)
        mutated = json.loads(FIXTURE.read_text(encoding="utf-8"))
        mutated["tensors"]["gelu_input_q16_16"]["values"][0][0] += 1
        with tempfile.TemporaryDirectory() as directory:
            fixture_path = Path(directory) / "mutated-fixture.json"
            fixture_path.write_text(json.dumps(mutated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture.*hash|fixture.*authority"):
                lowerer.run_gelu_sv(artifact, fixture_path)

    def test_mlp_fixture_replays_every_boundary(self):
        self.assertTrue(CAPTURE.is_file(), "missing authenticated MLP capture module")
        self.assertTrue(FIXTURE.is_file(), "missing authenticated MLP fixture")
        capture_mlp = load_capture()
        fixture = capture_mlp.verify_fixture(FIXTURE)
        capture_mlp.verify_eager_replay(FIXTURE)
        capture_mlp.verify_fixed_point_replay(FIXTURE)
        self.assertEqual(
            fixture["slice"]["c_fc"], {"rows": 4, "inputs": 64, "outputs": 256}
        )
        self.assertEqual(
            fixture["slice"]["c_proj"], {"rows": 4, "inputs": 256, "outputs": 64}
        )

    def test_fixture_has_complete_raw_authenticated_tensor_contract(self):
        capture_mlp = load_capture()
        fixture = capture_mlp.verify_fixture(FIXTURE)
        self.assertEqual(
            {name: record["shape"] for name, record in fixture["tensors"].items()},
            EXPECTED_SHAPES,
        )
        binding = fixture["tensor_fixture_receipt_sha256"]
        for record in fixture["tensors"].values():
            self.assertEqual(record["fixture_receipt_sha256"], binding)
            self.assertEqual(record["dtype"], "int64")
            self.assertRegex(record["canonical_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(record["little_endian_int64_sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(record["bytes"], 0)

    def test_fixture_rejects_tensor_tampering_even_with_resealed_outer_receipt(self):
        capture_mlp = load_capture()
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        fixture["tensors"]["c_fc_input_codes_i8"]["values"][0][0] += 1
        payload = {key: value for key, value in fixture.items() if key != "receipt_sha256"}
        fixture["receipt_sha256"] = canonical(payload)
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "tampered.json"
            candidate.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture tensor"):
                capture_mlp.verify_fixture(candidate)


if __name__ == "__main__":
    unittest.main()
