import copy
import json
import tempfile
import unittest
from pathlib import Path

import torch

from TinyStories import rc_serving_w4a8_integrated_contract as contract


def valid_phase_shapes() -> dict[str, dict[str, object]]:
    return {
        name: {
            "token": [],
            "logits": [6],
            "cache": [[1, 1, sequence_length, 2]] * 4,
        }
        for name, sequence_length in (
            ("prefill-8", 8),
            ("decode-8", 9),
            ("decode-9", 10),
        )
    }


class RcServingW4A8IntegratedContractTest(unittest.TestCase):
    def test_readback_manifest_is_dense_and_phase_ordered(self) -> None:
        manifest = contract.build_readback_manifest(valid_phase_shapes())

        self.assertEqual(
            [word["address"] for word in manifest["words"]],
            list(range(len(manifest["words"]))),
        )
        self.assertEqual(
            [region["phase"] for region in manifest["regions"]],
            list(contract.PHASE_NAMES),
        )
        self.assertEqual(manifest["argmax_tie_break"], "lowest-index")

    def test_manifest_orders_token_logits_then_cache_words(self) -> None:
        manifest = contract.build_readback_manifest(valid_phase_shapes())
        prefill_words = [
            word for word in manifest["words"] if word["phase"] == "prefill-8"
        ]

        self.assertEqual(prefill_words[0]["kind"], "token")
        self.assertEqual(
            [word["flat_index"] for word in prefill_words[1:7]], list(range(6))
        )
        self.assertTrue(all(word["kind"] == "logits" for word in prefill_words[1:7]))
        self.assertEqual(prefill_words[7]["kind"], "cache")
        self.assertEqual(prefill_words[7]["leaf"], 0)
        self.assertEqual(prefill_words[7]["flat_index"], 0)

    def test_manifest_rejects_missing_cache_leaf(self) -> None:
        manifest = contract.build_readback_manifest(valid_phase_shapes())
        broken = copy.deepcopy(manifest)
        broken["regions"][0]["cache_leaves"].pop()

        with self.assertRaisesRegex(ValueError, "four cache leaves"):
            contract.validate_readback_manifest(broken)

    def test_manifest_rejects_wrong_sequence_length(self) -> None:
        shapes = valid_phase_shapes()
        shapes["decode-8"]["cache"][0][2] = 8

        with self.assertRaisesRegex(ValueError, "sequence length"):
            contract.build_readback_manifest(shapes)

    def test_write_observation_is_deterministic_and_validated(self) -> None:
        manifest = contract.build_readback_manifest(valid_phase_shapes())
        observation = contract.IntegratedObservation(
            prompt_token_ids=(0, 1, 2, 3, 4, 5, 0, 1),
            phase_tokens=(1, 2, 3),
            phase_logits=((1, 2, 3, 4, 5, 6),) * 3,
            phase_cache_leaves=tuple(
                tuple(torch.zeros((1, 1, length, 2)) for _ in range(4))
                for length in (8, 9, 10)
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "observation.json"
            contract.write_integrated_observation(path, observation, manifest)
            first = path.read_bytes()
            contract.write_integrated_observation(path, observation, manifest)
            second = path.read_bytes()

        self.assertEqual(path.name, "observation.json")
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["schema"], contract.OBSERVATION_SCHEMA)
        self.assertEqual(payload["phase_tokens"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
