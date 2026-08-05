"""Byte-exact evidence helpers for the native DynamicCache serving trace."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import torch
from torch.utils._pytree import tree_flatten_with_path

from .rc_serving_contract import (
    SERVING_RC_MODEL_KEY,
    VOCAB_SIZE,
    ServingTrace,
    argmax_lowest,
)
from .rc_serving_source import run_native_call


_DYNAMIC_CACHE_SUPPORT_REGISTERED = False


def enable_hf_dynamic_cache_export_support() -> None:
    global _DYNAMIC_CACHE_SUPPORT_REGISTERED
    if _DYNAMIC_CACHE_SUPPORT_REGISTERED:
        return
    from transformers.integrations.executorch import (
        register_dynamic_cache_export_support,
    )

    register_dynamic_cache_export_support()
    _DYNAMIC_CACHE_SUPPORT_REGISTERED = True


def _raw_tensor_bytes(tensor: torch.Tensor) -> bytes:
    detached = tensor.detach().cpu().contiguous()
    return bytes(detached.view(torch.uint8).reshape(-1).tolist())


def tensor_record(tensor: torch.Tensor) -> dict[str, object]:
    detached = tensor.detach().cpu().contiguous()
    raw = _raw_tensor_bytes(detached)
    return {
        "dtype": str(detached.dtype),
        "shape": [int(dimension) for dimension in detached.shape],
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "little_endian_hex": raw.hex(),
    }


def _path_record(path: tuple[object, ...]) -> str:
    return "/".join(str(entry) for entry in path)


@dataclass
class NativeCacheSnapshot:
    schema: dict[str, object]
    leaves: tuple[torch.Tensor, ...]

    def record(self) -> dict[str, object]:
        return {
            "native_type": self.schema["native_type"],
            "tree_spec": self.schema["tree_spec"],
            "leaf_count": self.schema["leaf_count"],
            "leaves": [
                {
                    "ordinal": ordinal,
                    "path": self.schema["leaves"][ordinal]["path"],
                    "tensor": tensor_record(leaf),
                }
                for ordinal, leaf in enumerate(self.leaves)
            ],
        }


def snapshot_native_cache(cache: object) -> NativeCacheSnapshot:
    enable_hf_dynamic_cache_export_support()
    path_leaves, tree_spec = tree_flatten_with_path(cache)
    if not path_leaves:
        raise ValueError("native cache has no tensor leaves")
    leaves: list[torch.Tensor] = []
    schema_leaves: list[dict[str, object]] = []
    for ordinal, (path, leaf) in enumerate(path_leaves):
        if not isinstance(leaf, torch.Tensor):
            raise ValueError(f"native cache leaf {ordinal} is not a tensor")
        copied = leaf.detach().cpu().contiguous().clone()
        leaves.append(copied)
        schema_leaves.append(
            {
                "ordinal": ordinal,
                "path": _path_record(path),
                "dtype": str(copied.dtype),
                "shape": [int(dimension) for dimension in copied.shape],
            }
        )
    schema = {
        "native_type": (
            f"{type(cache).__module__}.{type(cache).__qualname__}"
        ),
        "tree_spec": str(tree_spec),
        "leaf_count": len(leaves),
        "leaves": schema_leaves,
    }
    return NativeCacheSnapshot(schema=schema, leaves=tuple(leaves))


def _assert_same_schema(
    before: NativeCacheSnapshot, after: NativeCacheSnapshot
) -> None:
    if before.schema["native_type"] != after.schema["native_type"]:
        raise ValueError("native cache type changed")
    if before.schema["tree_spec"] != after.schema["tree_spec"]:
        raise ValueError("native cache tree spec changed")
    if before.schema["leaf_count"] != after.schema["leaf_count"]:
        raise ValueError("native cache leaf count changed")
    for before_leaf, after_leaf in zip(
        before.schema["leaves"], after.schema["leaves"]
    ):
        if before_leaf["path"] != after_leaf["path"]:
            raise ValueError("native cache leaf path changed")
        if before_leaf["dtype"] != after_leaf["dtype"]:
            raise ValueError("native cache leaf dtype changed")


def _sequence_axis(
    before: NativeCacheSnapshot, after: NativeCacheSnapshot
) -> int:
    axes: set[int] = set()
    for before_leaf, after_leaf in zip(
        before.schema["leaves"], after.schema["leaves"]
    ):
        before_shape = tuple(before_leaf["shape"])
        after_shape = tuple(after_leaf["shape"])
        if len(before_shape) != len(after_shape):
            raise ValueError("native cache rank changed")
        growing = [
            axis
            for axis, (old, new) in enumerate(zip(before_shape, after_shape))
            if new == old + 1
        ]
        unchanged = [
            axis
            for axis, (old, new) in enumerate(zip(before_shape, after_shape))
            if new == old
        ]
        if len(growing) != 1 or len(unchanged) != len(before_shape) - 1:
            raise ValueError("native cache does not grow by one position")
        axes.add(growing[0])
    if len(axes) != 1:
        raise ValueError("native cache leaves disagree on sequence axis")
    return axes.pop()


def assert_cache_prefix_unchanged(
    before: NativeCacheSnapshot,
    after: NativeCacheSnapshot,
    valid_length: int,
) -> int:
    _assert_same_schema(before, after)
    axis = _sequence_axis(before, after)
    for before_leaf, after_leaf in zip(before.leaves, after.leaves):
        before_prefix = before_leaf.narrow(axis, 0, valid_length)
        after_prefix = after_leaf.narrow(axis, 0, valid_length)
        if _raw_tensor_bytes(before_prefix) != _raw_tensor_bytes(after_prefix):
            raise ValueError("native cache valid prefix was mutated")
    return axis


def _phase_record(
    phase: Any,
    input_ids: torch.Tensor,
    logits: torch.Tensor,
    cache: NativeCacheSnapshot,
) -> dict[str, object]:
    last_logits = logits[0, -1, :].detach().cpu().contiguous()
    if last_logits.numel() != VOCAB_SIZE:
        raise ValueError("native logits do not have six vocabulary values")
    return {
        "name": phase.name,
        "input_token_ids": [int(value) for value in input_ids[0].tolist()],
        "cache_length_before": phase.cache_length_before,
        "cache_length_after": phase.cache_length_after,
        "cache_position": list(phase.cache_positions),
        "last_logits": tensor_record(last_logits),
        "greedy_token_id": argmax_lowest(last_logits.tolist()),
        "cache_snapshot": cache.record(),
    }


def run_native_trace(model: object, trace: ServingTrace) -> dict[str, object]:
    enable_hf_dynamic_cache_export_support()
    prompt = torch.tensor([trace.prompt_token_ids], dtype=torch.long)
    prefill, decode_8, decode_9 = trace.phases

    prefill_logits, cache_8 = run_native_call(model, prefill, prompt, None)
    snapshot_8 = snapshot_native_cache(cache_8)
    token_8 = argmax_lowest(prefill_logits[0, -1, :].tolist())
    prefill_record = _phase_record(
        prefill, prompt, prefill_logits, snapshot_8
    )

    decode_8_input = torch.tensor([[token_8]], dtype=torch.long)
    decode_8_logits, cache_9 = run_native_call(
        model, decode_8, decode_8_input, cache_8
    )
    snapshot_9 = snapshot_native_cache(cache_9)
    axis_8_to_9 = assert_cache_prefix_unchanged(snapshot_8, snapshot_9, 8)
    token_9 = argmax_lowest(decode_8_logits[0, -1, :].tolist())
    decode_8_record = _phase_record(
        decode_8, decode_8_input, decode_8_logits, snapshot_9
    )

    decode_9_input = torch.tensor([[token_9]], dtype=torch.long)
    decode_9_logits, cache_10 = run_native_call(
        model, decode_9, decode_9_input, cache_9
    )
    snapshot_10 = snapshot_native_cache(cache_10)
    axis_9_to_10 = assert_cache_prefix_unchanged(snapshot_9, snapshot_10, 9)
    decode_9_record = _phase_record(
        decode_9, decode_9_input, decode_9_logits, snapshot_10
    )
    if axis_8_to_9 != axis_9_to_10:
        raise ValueError("native cache sequence axis changed during decode")

    return {
        "schema_version": 1,
        "artifact_kind": "native-serving-reference",
        "model_key": SERVING_RC_MODEL_KEY,
        "numeric_format": "native-fp32-source",
        "quantization_status": "unproven",
        "trace": {
            "prompt_token_ids": list(trace.prompt_token_ids),
            "phases": [phase.name for phase in trace.phases],
        },
        "native_cache_schema": snapshot_8.schema,
        "cache_sequence_axis": axis_8_to_9,
        "phases": [prefill_record, decode_8_record, decode_9_record],
    }


def _jsonable_model_config(model: torch.nn.Module) -> dict[str, object]:
    config = model.config.to_dict()
    return json.loads(json.dumps(config, sort_keys=True, default=str))
