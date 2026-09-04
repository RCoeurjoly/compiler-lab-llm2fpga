import copy
import unittest

from TinyStories.rc_serving_w4a8_contract import (
    W4A8_MODEL_KEY,
    accumulator_bounds,
    validate_manifest,
)


def valid_manifest_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "model_key": "tinystories-w4a8-rc-serving-mask10-vocab6-width2",
        "quantization": {
            "weights": {"bits": 4, "signed": True, "minimum": -8, "maximum": 7},
            "activations": {
                "bits": 8,
                "signed": True,
                "minimum": -128,
                "maximum": 127,
            },
            "rounding": "round-to-nearest-even",
            "saturation": "signed-clamp",
        },
        "packing": {
            "nibble_order": "low-even-high-odd",
            "padding": "zero-high-nibble",
        },
        "phases": ["prefill-8", "decode-8", "decode-9"],
        "tensors": [
            {
                "name": "linear.weight",
                "shape": [2, 3],
                "bits": 4,
                "signed": True,
                "element_count": 6,
                "packed_byte_count": 3,
                "sha256": "a" * 64,
            }
        ],
    }


class RcServingW4A8ContractTest(unittest.TestCase):
    def test_w4a8_contract_has_exact_ranges_and_accumulator_bound(self) -> None:
        self.assertEqual(
            W4A8_MODEL_KEY,
            "tinystories-w4a8-rc-serving-mask10-vocab6-width2",
        )
        self.assertEqual(accumulator_bounds(2), (-2032, 2048))

    def test_manifest_rejects_wrong_packing_order(self) -> None:
        payload = copy.deepcopy(valid_manifest_payload())
        payload["packing"]["nibble_order"] = "high-even-low-odd"
        with self.assertRaisesRegex(ValueError, "nibble_order"):
            validate_manifest(payload)

    def test_manifest_accepts_the_canonical_contract(self) -> None:
        manifest = validate_manifest(valid_manifest_payload())
        self.assertEqual(manifest.model_key, W4A8_MODEL_KEY)
        self.assertEqual(manifest.tensors[0].shape, (2, 3))

    def test_manifest_rejects_duplicate_tensor_names(self) -> None:
        payload = valid_manifest_payload()
        payload["tensors"].append(copy.deepcopy(payload["tensors"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_manifest(payload)

    def test_manifest_rejects_bad_packed_byte_count(self) -> None:
        payload = valid_manifest_payload()
        payload["tensors"][0]["packed_byte_count"] = 4
        with self.assertRaisesRegex(ValueError, "packed_byte_count"):
            validate_manifest(payload)

    def test_accumulator_bounds_requires_positive_reduction(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            accumulator_bounds(0)


if __name__ == "__main__":
    unittest.main()
