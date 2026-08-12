"""Explicit tensor-only cache ABI used at the PT2E compiler boundary."""

from __future__ import annotations

from collections.abc import Sequence

import torch
from transformers import DynamicCache
from transformers.cache_utils import DynamicLayer

from .rc_serving_contract import ServingPhase


def _validate_tensor(tensor: object, ordinal: int) -> torch.Tensor:
    if not isinstance(tensor, torch.Tensor):
        raise ValueError(f"cache leaf {ordinal} is not a tensor")
    if tensor.ndim != 4:
        raise ValueError(f"cache leaf {ordinal} must have rank four")
    return tensor


def flatten_dynamic_cache(
    cache: object, *, expected_layers: int
) -> tuple[torch.Tensor, ...]:
    if not isinstance(cache, DynamicCache):
        raise ValueError("compiler cache boundary requires DynamicCache")
    legacy = cache.to_legacy_cache()
    if len(legacy) != expected_layers:
        raise ValueError(f"cache must contain exactly {expected_layers} layers")
    leaves: list[torch.Tensor] = []
    for layer, pair in enumerate(legacy):
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError(f"cache layer {layer} must contain key and value")
        leaves.extend(
            (_validate_tensor(pair[0], 2 * layer), _validate_tensor(pair[1], 2 * layer + 1))
        )
    return tuple(leaves)


def reconstruct_dynamic_cache(
    leaves: Sequence[torch.Tensor], *, expected_layers: int
) -> DynamicCache:
    expected_leaves = 2 * expected_layers
    if len(leaves) != expected_leaves:
        word = "four" if expected_leaves == 4 else str(expected_leaves)
        raise ValueError(f"cache boundary requires exactly {word} K/V tensors")
    cache = DynamicCache()
    for layer in range(expected_layers):
        key = _validate_tensor(leaves[2 * layer], 2 * layer)
        value = _validate_tensor(leaves[2 * layer + 1], 2 * layer + 1)
        cache_layer = DynamicLayer()
        cache_layer.keys = key
        cache_layer.values = value
        cache_layer.is_initialized = True
        cache.layers.append(cache_layer)
    return cache


class TensorCachePhaseWrapper(torch.nn.Module):
    def __init__(
        self, model: torch.nn.Module, phase: ServingPhase, *, expected_layers: int
    ) -> None:
        super().__init__()
        self.model = model
        self.phase = phase
        self.expected_layers = expected_layers

    def forward(
        self, input_ids: torch.Tensor, *cache_leaves: torch.Tensor
    ) -> tuple[torch.Tensor, ...]:
        cache = (
            None
            if self.phase.cache_length_before == 0
            else reconstruct_dynamic_cache(
                cache_leaves, expected_layers=self.expected_layers
            )
        )
        output = self.model(
            input_ids,
            past_key_values=cache,
            use_cache=True,
            return_dict=False,
            attention_mask=torch.ones(
                (1, self.phase.cache_length_after), dtype=torch.long
            ),
            cache_position=torch.tensor(self.phase.cache_positions, dtype=torch.long),
        )
        if not isinstance(output, tuple) or len(output) < 2:
            raise RuntimeError("wrapped source model did not return logits and cache")
        logits, returned_cache = output[0], output[1]
        if not isinstance(logits, torch.Tensor):
            raise RuntimeError("wrapped source logits are not a tensor")
        return (logits,) + flatten_dynamic_cache(
            returned_cache, expected_layers=self.expected_layers
        )
