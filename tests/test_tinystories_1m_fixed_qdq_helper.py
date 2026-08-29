from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/tinystories_1m_fixed_qdq_helper.py"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
SOFTMAX = ROOT / "artifacts/reference/tinystories-1m-fixed-softmax-checkpoints.json"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "tinystories_1m_fixed_qdq_helper", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyStories1MFixedQdqHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_quantize_uses_half_away_rounding_and_saturating_int8(self) -> None:
        values = [-1000, -257, -255, -3, -1, 0, 1, 3, 255, 257, 1000]
        scales = [512] * len(values)
        self.assertEqual(
            self.module.quantize_q16_to_int8(values, scales),
            [-128, -128, -128, -2, -1, 0, 1, 2, 127, 127, 127],
        )

    def test_dequantize_uses_signed_half_away_shift_by_8(self) -> None:
        self.assertEqual(
            self.module.dequantize_int8_to_q16([-3, -1, 0, 1, 3], [384] * 5),
            [-5, -2, 0, 2, 5],
        )

    def test_scale_validation_rejects_bool_nonpositive_malformed_and_out_of_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "same non-zero length"):
            self.module.quantize_q16_to_int8([1], [])
        with self.assertRaisesRegex(ValueError, "same non-zero length"):
            self.module.quantize_q16_to_int8([], [])
        with self.assertRaisesRegex(ValueError, "same non-zero length"):
            self.module.dequantize_int8_to_q16([], [])
        with self.assertRaisesRegex(ValueError, "integer"):
            self.module.quantize_q16_to_int8([1], [True])
        for scale in (0, -1):
            with self.subTest(scale=scale), self.assertRaisesRegex(ValueError, "positive"):
                self.module.quantize_q16_to_int8([1], [scale])
        with self.assertRaisesRegex(ValueError, "24-bit"):
            self.module.quantize_q16_to_int8([1], [1 << 24])

    def test_value_validation_rejects_bool_and_non_integer_domain(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer"):
            self.module.quantize_q16_to_int8([1.25], [512])
        with self.assertRaisesRegex(ValueError, "integer"):
            self.module.quantize_q16_to_int8([True], [512])
        with self.assertRaisesRegex(ValueError, "int8"):
            self.module.dequantize_int8_to_q16([128], [512])

    def test_profile_validation_requires_content_bound_identity(self) -> None:
        profile = self.module.load_fixed_hardware_profile(PROFILE)
        self.assertEqual(
            profile["identity"]["contract_sha256"],
            self.module.CANONICAL_CONTRACT_SHA256,
        )
        self.assertEqual(
            profile["profile_sha256"],
            self.module.CANONICAL_PROFILE_SHA256,
        )
        tampered = copy.deepcopy(profile)
        tampered["identity"]["contract_sha256"] = "0" * 64
        tampered["profile_sha256"] = self.module.profile_sha256(tampered)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_text(
                json.dumps(tampered, sort_keys=True, allow_nan=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.FixedQdqHelperError, "profile_artifact_identity_mismatch"
            ):
                self.module.load_fixed_hardware_profile(path)

    def test_block0_token3_qk_fixture_binds_authenticated_package_and_profile_metadata(self) -> None:
        fixture = self.module.load_block0_token3_qk_fixture(PROFILE, SOFTMAX)
        self.assertEqual(
            fixture["slice"],
            {
                "kind": "one_transformer_block_token_step",
                "block_index": 0,
                "token_index": 3,
                "prompt_tokens": [7454, 2402, 257, 640],
                "next_token": 11,
                "num_heads": 16,
                "head_dim": 4,
                "sequence_length": 4,
            },
        )
        self.assertEqual(fixture["q_shape"], [16, 4])
        self.assertEqual(fixture["k_shape"], [16, 4])
        self.assertEqual(
            fixture["identity"]["package_manifest_sha256"],
            "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35",
        )
        self.assertEqual(
            fixture["profile_binding"]["profile_artifact_sha256"],
            self.module.CANONICAL_PROFILE_ARTIFACT_SHA256,
        )
        self.assertEqual(fixture["q_q16_16"][0], [-13594, 6489, -8875, -30803])
        self.assertEqual(fixture["k_q16_16"][0], [83112, 4965, 40799, 0])
        self.assertEqual(len(fixture["q_q16_16"]), 16)
        self.assertEqual(len(fixture["k_q16_16"]), 16)
        self.assertEqual(fixture["k_q16_16"][-1], [-22214, 24867, 4907, -49917])

    def test_fixture_loader_rejects_rehashed_profile_binding_mismatch(self) -> None:
        artifact = json.loads(SOFTMAX.read_text(encoding="utf-8"))
        artifact = copy.deepcopy(artifact)
        artifact["profile_binding"]["profile_sha256"] = "0" * 64
        artifact["sha256"] = self.module.canonical_sha256(
            {key: value for key, value in artifact.items() if key != "sha256"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "softmax.json"
            path.write_text(
                json.dumps(artifact, sort_keys=True, allow_nan=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.FixedQdqHelperError, "softmax_artifact_identity_mismatch"
            ):
                self.module.load_block0_token3_qk_fixture(PROFILE, path)

    def test_fixture_loader_rejects_rehashed_contract_identity_mismatch(self) -> None:
        artifact = json.loads(SOFTMAX.read_text(encoding="utf-8"))
        artifact = copy.deepcopy(artifact)
        artifact["identity"]["contract_sha256"] = "0" * 64
        artifact["sha256"] = self.module.canonical_sha256(
            {key: value for key, value in artifact.items() if key != "sha256"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "softmax.json"
            path.write_text(
                json.dumps(artifact, sort_keys=True, allow_nan=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.FixedQdqHelperError, "softmax_artifact_identity_mismatch"
            ):
                self.module.load_block0_token3_qk_fixture(PROFILE, path)

    def test_fixture_loader_rejects_rehashed_package_manifest_identity_mismatch(self) -> None:
        artifact = json.loads(SOFTMAX.read_text(encoding="utf-8"))
        artifact = copy.deepcopy(artifact)
        artifact["identity"]["package_manifest_sha256"] = "0" * 64
        artifact["sha256"] = self.module.canonical_sha256(
            {key: value for key, value in artifact.items() if key != "sha256"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "softmax.json"
            path.write_text(
                json.dumps(artifact, sort_keys=True, allow_nan=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.FixedQdqHelperError, "softmax_artifact_identity_mismatch"
            ):
                self.module.load_block0_token3_qk_fixture(PROFILE, path)


if __name__ == "__main__":
    unittest.main()
