import unittest

import torch
from transformers import DynamicCache

from TinyStories.rc_serving_w4a8_cache_abi import (
    TensorCachePhaseWrapper,
    flatten_dynamic_cache,
    reconstruct_dynamic_cache,
)
from TinyStories.rc_serving_contract import phase_by_name
from TinyStories.rc_serving_w4a8_source import snapshot_cache


def sample_cache() -> DynamicCache:
    layers = []
    for layer in range(2):
        key = torch.arange(8, dtype=torch.float32).reshape(1, 1, 4, 2) + layer * 100
        value = key + 50
        layers.append((key, value))
    return DynamicCache.from_legacy_cache(tuple(layers))


class RcServingW4A8CacheAbiTest(unittest.TestCase):
    def test_tensor_wrapper_matches_native_cache_call(self) -> None:
        class FakeModel(torch.nn.Module):
            def forward(self, input_ids, past_key_values, **kwargs):
                cache = past_key_values
                token = input_ids.to(torch.float32).reshape(1, 1, 1, 1).expand(-1, -1, -1, 2)
                for layer in range(2):
                    cache.update(token + layer, token + layer + 10, layer)
                return input_ids.to(torch.float32), cache

        phase = phase_by_name("decode-8")
        source_cache = sample_cache()
        native_cache = reconstruct_dynamic_cache(
            flatten_dynamic_cache(source_cache, expected_layers=2), expected_layers=2
        )
        native = FakeModel()(
            torch.tensor([[3]]),
            past_key_values=native_cache,
            use_cache=True,
            return_dict=False,
            attention_mask=torch.ones((1, 9), dtype=torch.long),
            cache_position=torch.tensor([8]),
        )
        wrapper = TensorCachePhaseWrapper(FakeModel(), phase, expected_layers=2)
        wrapped = wrapper(
            torch.tensor([[3]]),
            *flatten_dynamic_cache(source_cache, expected_layers=2),
        )
        self.assertTrue(torch.equal(wrapped[0], native[0]))
        self.assertEqual(
            [tensor.numpy().tobytes() for tensor in wrapped[1:]],
            [
                tensor.numpy().tobytes()
                for tensor in flatten_dynamic_cache(native[1], expected_layers=2)
            ],
        )

    def test_flatten_orders_key_then_value_for_each_layer(self) -> None:
        cache = sample_cache()
        flat = flatten_dynamic_cache(cache, expected_layers=2)
        legacy = cache.to_legacy_cache()
        self.assertEqual(len(flat), 4)
        self.assertTrue(torch.equal(flat[0], legacy[0][0]))
        self.assertTrue(torch.equal(flat[1], legacy[0][1]))
        self.assertTrue(torch.equal(flat[2], legacy[1][0]))
        self.assertTrue(torch.equal(flat[3], legacy[1][1]))

    def test_reconstruction_is_byte_exact(self) -> None:
        flat = flatten_dynamic_cache(sample_cache(), expected_layers=2)
        rebuilt = reconstruct_dynamic_cache(flat, expected_layers=2)
        rebuilt_flat = flatten_dynamic_cache(rebuilt, expected_layers=2)
        self.assertEqual(
            [tensor.numpy().tobytes() for tensor in rebuilt_flat],
            [tensor.numpy().tobytes() for tensor in flat],
        )

    def test_reconstruction_does_not_insert_rank_one_empty_concat(self) -> None:
        class CacheRoundTrip(torch.nn.Module):
            def forward(self, *leaves):
                cache = reconstruct_dynamic_cache(leaves, expected_layers=2)
                return flatten_dynamic_cache(cache, expected_layers=2)

        flat = flatten_dynamic_cache(sample_cache(), expected_layers=2)
        exported = torch.export.export(CacheRoundTrip(), flat, strict=False)
        graph = str(exported.graph)
        self.assertNotIn("aten.cat", graph)
        self.assertNotIn("lift_fresh_copy", graph)

    def test_snapshot_cache_isolated_from_later_mutation(self) -> None:
        original = sample_cache()
        copied = snapshot_cache(original, expected_layers=2)
        token = torch.zeros((1, 1, 1, 2))
        original.update(token, token, 0)
        self.assertEqual(
            flatten_dynamic_cache(copied, expected_layers=2)[0].shape[-2], 4
        )
        self.assertEqual(
            flatten_dynamic_cache(original, expected_layers=2)[0].shape[-2], 5
        )

    def test_reconstruction_rejects_wrong_leaf_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "four K/V tensors"):
            reconstruct_dynamic_cache((torch.zeros(1),), expected_layers=2)

    def test_flatten_rejects_non_rank_four_cache_tensor(self) -> None:
        cache = DynamicCache.from_legacy_cache(
            ((torch.zeros(1, 2), torch.zeros(1, 2)),) * 2
        )
        with self.assertRaisesRegex(ValueError, "rank four"):
            flatten_dynamic_cache(cache, expected_layers=2)


if __name__ == "__main__":
    unittest.main()
