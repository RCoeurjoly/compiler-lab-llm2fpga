"""One-call stateful W4A8 serving program and its exact observation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import torch

from .rc_serving_contract import (
    NUM_LAYERS,
    PHASE_NAMES,
    PREFILL_LENGTH,
    VOCAB_SIZE,
    phase_by_name,
    validate_token_ids,
)
from .rc_serving_source import native_call_kwargs
from .rc_serving_w4a8_cache_abi import (
    flatten_dynamic_cache,
    reconstruct_dynamic_cache,
)
from .rc_serving_w4a8_integrated_contract import IntegratedObservation


_PHASES = tuple(phase_by_name(name) for name in PHASE_NAMES)
_TENSOR_CACHE_ABI_PATHS = (
    "['key_cache']/[0]",
    "['value_cache']/[0]",
    "['key_cache']/[1]",
    "['value_cache']/[1]",
)


def native_cache_records_in_tensor_abi_order(
    leaves: Sequence[Mapping[str, object]],
) -> list[object]:
    """Map native pytree K-all/V-all records to layer-local K/V ABI order."""

    by_path: dict[str, object] = {}
    for leaf in leaves:
        path = leaf.get("path")
        if not isinstance(path, str) or path not in _TENSOR_CACHE_ABI_PATHS:
            raise ValueError(f"unexpected native cache leaf path: {path!r}")
        if path in by_path:
            raise ValueError(f"duplicate native cache leaf path: {path}")
        if "tensor" not in leaf:
            raise ValueError(f"native cache leaf {path} has no tensor record")
        by_path[path] = leaf["tensor"]
    if set(by_path) != set(_TENSOR_CACHE_ABI_PATHS):
        raise ValueError("native cache record does not contain two K/V layers")
    return [by_path[path] for path in _TENSOR_CACHE_ABI_PATHS]


class IntegratedW4A8Module(torch.nn.Module):
    """Run prefill and two cached greedy decode steps in one forward call."""

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def _phase(
        self,
        input_ids: torch.Tensor,
        phase_index: int,
        cache_leaves: tuple[torch.Tensor, ...],
    ) -> tuple[torch.Tensor, torch.Tensor, tuple[torch.Tensor, ...]]:
        phase = _PHASES[phase_index]
        cache = (
            None
            if phase_index == 0
            else reconstruct_dynamic_cache(cache_leaves, expected_layers=NUM_LAYERS)
        )
        output = self.model(input_ids, **native_call_kwargs(phase, cache))
        if not isinstance(output, tuple) or len(output) < 2:
            raise RuntimeError("integrated source model did not return logits and cache")
        logits, returned_cache = output[0], output[1]
        if not isinstance(logits, torch.Tensor):
            raise RuntimeError("integrated source logits are not a tensor")
        expected_shape = (1, phase.input_length, VOCAB_SIZE)
        if tuple(logits.shape) != expected_shape:
            raise RuntimeError(
                f"{phase.name} returned logits shape {tuple(logits.shape)}, "
                f"expected {expected_shape}"
            )
        last_logits = logits[:, -1, :]
        token = torch.argmax(last_logits, dim=-1, keepdim=True)
        leaves = flatten_dynamic_cache(returned_cache, expected_layers=NUM_LAYERS)
        return token, last_logits, leaves

    def forward(self, prompt: torch.Tensor) -> tuple[torch.Tensor, ...]:
        if tuple(prompt.shape) != (1, PREFILL_LENGTH):
            raise ValueError(f"integrated prompt must have shape [1, {PREFILL_LENGTH}]")

        token_8, logits_8, cache_8 = self._phase(prompt, 0, ())
        token_9, logits_9, cache_9 = self._phase(token_8, 1, cache_8)
        token_10, logits_10, cache_10 = self._phase(token_9, 2, cache_9)
        return (
            token_8,
            token_9,
            token_10,
            logits_8,
            *cache_8,
            logits_9,
            *cache_9,
            logits_10,
            *cache_10,
        )


def run_integrated_eager(
    module: IntegratedW4A8Module, prompt: torch.Tensor
) -> IntegratedObservation:
    if tuple(prompt.shape) != (1, PREFILL_LENGTH):
        raise ValueError(f"integrated prompt must have shape [1, {PREFILL_LENGTH}]")
    prompt_ids = validate_token_ids(
        tuple(int(value) for value in prompt.reshape(-1).tolist()), PREFILL_LENGTH
    )
    with torch.no_grad():
        flat = module(prompt)
    if len(flat) != 18:
        raise RuntimeError("integrated module must return exactly 18 tensors")

    tokens = tuple(int(value.item()) for value in flat[:3])
    logits: list[tuple[int | float, ...]] = []
    phase_caches: list[tuple[torch.Tensor, ...]] = []
    for offset in (3, 8, 13):
        phase_logits = flat[offset].detach().cpu().contiguous().reshape(-1)
        if phase_logits.numel() != VOCAB_SIZE:
            raise RuntimeError("integrated phase logits do not match vocabulary size")
        logits.append(tuple(phase_logits.tolist()))
        phase_caches.append(
            tuple(
                tensor.detach().cpu().contiguous().clone()
                for tensor in flat[offset + 1 : offset + 5]
            )
        )
    return IntegratedObservation(
        prompt_token_ids=prompt_ids,
        phase_tokens=tokens,
        phase_logits=(logits[0], logits[1], logits[2]),
        phase_cache_leaves=tuple(phase_caches),
    )


def _first_sequence_mismatch(expected: Sequence[object], actual: Sequence[object]) -> int:
    if len(expected) != len(actual):
        return min(len(expected), len(actual))
    return next(
        (index for index, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
        -1,
    )


def assert_integrated_observation_equal(
    expected: IntegratedObservation, actual: IntegratedObservation
) -> None:
    if tuple(expected.prompt_token_ids) != tuple(actual.prompt_token_ids):
        raise AssertionError("integrated prompt token IDs differ")
    if expected.phase_tokens != actual.phase_tokens:
        index = _first_sequence_mismatch(expected.phase_tokens, actual.phase_tokens)
        phase = PHASE_NAMES[index] if index < len(PHASE_NAMES) else "length"
        raise AssertionError(f"{phase} selected token differs")

    for phase_index, phase in enumerate(PHASE_NAMES):
        expected_logits = expected.phase_logits[phase_index]
        actual_logits = actual.phase_logits[phase_index]
        mismatch = _first_sequence_mismatch(expected_logits, actual_logits)
        if mismatch != -1:
            raise AssertionError(f"{phase} logits differ at flat index {mismatch}")

        expected_leaves = expected.phase_cache_leaves[phase_index]
        actual_leaves = actual.phase_cache_leaves[phase_index]
        if len(expected_leaves) != len(actual_leaves):
            raise AssertionError(f"{phase} cache leaf count differs")
        for leaf_index, (expected_tensor, actual_tensor) in enumerate(
            zip(expected_leaves, actual_leaves)
        ):
            if tuple(expected_tensor.shape) != tuple(actual_tensor.shape):
                raise AssertionError(f"{phase} cache leaf {leaf_index} shape differs")
            equal = torch.eq(expected_tensor, actual_tensor).reshape(-1)
            if not bool(torch.all(equal)):
                mismatch = int(torch.nonzero(~equal, as_tuple=False)[0].item())
                raise AssertionError(
                    f"{phase} cache leaf {leaf_index} differs at flat index {mismatch}"
                )
