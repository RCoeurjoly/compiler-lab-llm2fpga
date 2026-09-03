from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json"
CAPTURE = ROOT / "TinyStories/capture_fixed_point_mlp_crossing_slice.py"

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


def canonical(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class FixedPointMlpCrossingTest(unittest.TestCase):
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
