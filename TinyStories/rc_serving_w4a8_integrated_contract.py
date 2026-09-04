"""Observable contract for one integrated stateful W4A8 RTL invocation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import torch

from .rc_serving_contract import PREFILL_LENGTH, VOCAB_SIZE, validate_token_ids
from .rc_serving_evidence import tensor_record
from .rc_serving_w4a8_contract import PHASE_NAMES, W4A8_MODEL_KEY


OBSERVATION_SCHEMA = "rc-serving-w4a8-integrated-observation-v1"
READBACK_SCHEMA = "rc-serving-w4a8-integrated-readback-v1"
ARGMAX_TIE_BREAK = "lowest-index"
CACHE_LEAF_COUNT = 4
_PHASE_SEQUENCE_LENGTHS = dict(zip(PHASE_NAMES, (8, 9, 10)))


@dataclass(frozen=True)
class IntegratedObservation:
    prompt_token_ids: Sequence[int]
    phase_tokens: tuple[int, int, int]
    phase_logits: tuple[Sequence[int | float], Sequence[int | float], Sequence[int | float]]
    phase_cache_leaves: Sequence[Sequence[torch.Tensor]]


def _shape(value: object, field: str, *, allow_scalar: bool = False) -> list[int]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} shape must be an array")
    dimensions = list(value)
    if allow_scalar and not dimensions:
        return dimensions
    if not dimensions or not all(
        isinstance(dimension, int)
        and not isinstance(dimension, bool)
        and dimension > 0
        for dimension in dimensions
    ):
        raise ValueError(f"{field} shape dimensions must be positive integers")
    return dimensions


def _element_count(shape: Sequence[int]) -> int:
    return math.prod(shape) if shape else 1


def _word(
    address: int,
    phase: str,
    kind: str,
    flat_index: int,
    *,
    leaf: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "address": address,
        "phase": phase,
        "kind": kind,
        "flat_index": flat_index,
        "width": 64 if kind == "token" else 32,
        "signed": False,
        "encoding": "unsigned-integer" if kind == "token" else "raw-tensor-bits",
    }
    if leaf is not None:
        payload["leaf"] = leaf
    return payload


def build_readback_manifest(
    phase_shapes: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if set(phase_shapes) != set(PHASE_NAMES):
        raise ValueError("phase shapes must contain the three canonical phases")

    address = 0
    words: list[dict[str, object]] = []
    regions: list[dict[str, object]] = []
    for phase in PHASE_NAMES:
        raw = phase_shapes[phase]
        token_shape = _shape(raw.get("token"), f"{phase} token", allow_scalar=True)
        if token_shape:
            raise ValueError(f"{phase} token must be scalar")
        logits_shape = _shape(raw.get("logits"), f"{phase} logits")
        if logits_shape != [VOCAB_SIZE]:
            raise ValueError(f"{phase} logits must have shape [{VOCAB_SIZE}]")
        cache_shapes = raw.get("cache")
        if not isinstance(cache_shapes, Sequence) or isinstance(cache_shapes, (str, bytes)):
            raise ValueError(f"{phase} cache must be an array")
        if len(cache_shapes) != CACHE_LEAF_COUNT:
            raise ValueError(f"{phase} must contain four cache leaves")

        region_start = address
        words.append(_word(address, phase, "token", 0))
        token_address = address
        address += 1

        logits_start = address
        for flat_index in range(VOCAB_SIZE):
            words.append(_word(address, phase, "logits", flat_index))
            address += 1

        cache_regions: list[dict[str, object]] = []
        expected_sequence_length = _PHASE_SEQUENCE_LENGTHS[phase]
        for leaf, raw_shape in enumerate(cache_shapes):
            shape = _shape(raw_shape, f"{phase} cache leaf {leaf}")
            if len(shape) != 4:
                raise ValueError(f"{phase} cache leaf {leaf} must be rank four")
            if shape[2] != expected_sequence_length:
                raise ValueError(
                    f"{phase} cache leaf {leaf} sequence length must equal "
                    f"{expected_sequence_length}"
                )
            leaf_start = address
            for flat_index in range(_element_count(shape)):
                words.append(_word(address, phase, "cache", flat_index, leaf=leaf))
                address += 1
            cache_regions.append(
                {
                    "leaf": leaf,
                    "shape": shape,
                    "start_address": leaf_start,
                    "word_count": _element_count(shape),
                }
            )

        regions.append(
            {
                "phase": phase,
                "start_address": region_start,
                "word_count": address - region_start,
                "token_address": token_address,
                "logits": {
                    "shape": logits_shape,
                    "start_address": logits_start,
                    "word_count": VOCAB_SIZE,
                },
                "cache_leaves": cache_regions,
            }
        )

    manifest: dict[str, object] = {
        "schema": READBACK_SCHEMA,
        "model_key": W4A8_MODEL_KEY,
        "phases": list(PHASE_NAMES),
        "argmax_tie_break": ARGMAX_TIE_BREAK,
        "address_count": address,
        "regions": regions,
        "words": words,
    }
    validate_readback_manifest(manifest)
    return manifest


def validate_readback_manifest(raw: Mapping[str, object]) -> None:
    if raw.get("schema") != READBACK_SCHEMA:
        raise ValueError("unsupported integrated readback schema")
    if raw.get("model_key") != W4A8_MODEL_KEY:
        raise ValueError("integrated readback model key does not match")
    if raw.get("phases") != list(PHASE_NAMES):
        raise ValueError("integrated readback phases are not canonical")
    if raw.get("argmax_tie_break") != ARGMAX_TIE_BREAK:
        raise ValueError("argmax tie break must be lowest-index")

    regions = raw.get("regions")
    words = raw.get("words")
    if not isinstance(regions, list) or len(regions) != len(PHASE_NAMES):
        raise ValueError("integrated readback must contain three phase regions")
    if not isinstance(words, list):
        raise ValueError("integrated readback words must be an array")
    if raw.get("address_count") != len(words):
        raise ValueError("integrated readback address count does not match words")
    if [word.get("address") for word in words if isinstance(word, Mapping)] != list(
        range(len(words))
    ):
        raise ValueError("integrated readback word addresses must be dense")

    for region, phase in zip(regions, PHASE_NAMES):
        if not isinstance(region, Mapping) or region.get("phase") != phase:
            raise ValueError("integrated readback regions are not phase ordered")
        leaves = region.get("cache_leaves")
        if not isinstance(leaves, list) or len(leaves) != CACHE_LEAF_COUNT:
            raise ValueError(f"{phase} must contain four cache leaves")
        for leaf_number, leaf in enumerate(leaves):
            if not isinstance(leaf, Mapping) or leaf.get("leaf") != leaf_number:
                raise ValueError(f"{phase} cache leaves are not canonically ordered")
            shape = _shape(leaf.get("shape"), f"{phase} cache leaf {leaf_number}")
            if len(shape) != 4 or shape[2] != _PHASE_SEQUENCE_LENGTHS[phase]:
                raise ValueError(f"{phase} cache leaf {leaf_number} sequence length is invalid")
            if leaf.get("word_count") != _element_count(shape):
                raise ValueError(f"{phase} cache leaf {leaf_number} word count is invalid")


def _validate_observation(
    observation: IntegratedObservation, manifest: Mapping[str, object]
) -> None:
    validate_token_ids(observation.prompt_token_ids, PREFILL_LENGTH)
    if len(observation.phase_tokens) != len(PHASE_NAMES) or any(
        not isinstance(token, int)
        or isinstance(token, bool)
        or not 0 <= token < VOCAB_SIZE
        for token in observation.phase_tokens
    ):
        raise ValueError("phase tokens must contain three legal token IDs")
    if len(observation.phase_logits) != len(PHASE_NAMES) or any(
        len(logits) != VOCAB_SIZE for logits in observation.phase_logits
    ):
        raise ValueError("phase logits must contain three vocabulary vectors")
    if len(observation.phase_cache_leaves) != len(PHASE_NAMES):
        raise ValueError("observation must contain three phase caches")

    regions = manifest["regions"]
    for phase_index, (leaves, region) in enumerate(
        zip(observation.phase_cache_leaves, regions)
    ):
        if len(leaves) != CACHE_LEAF_COUNT:
            raise ValueError(f"{PHASE_NAMES[phase_index]} must contain four cache leaves")
        for tensor, leaf_region in zip(leaves, region["cache_leaves"]):
            if list(tensor.shape) != leaf_region["shape"]:
                raise ValueError(
                    f"{PHASE_NAMES[phase_index]} cache tensor shape does not match manifest"
                )


def write_integrated_observation(
    path: Path,
    observation: IntegratedObservation,
    manifest: Mapping[str, object],
) -> None:
    validate_readback_manifest(manifest)
    _validate_observation(observation, manifest)
    payload = {
        "schema": OBSERVATION_SCHEMA,
        "model_key": W4A8_MODEL_KEY,
        "prompt_token_ids": list(observation.prompt_token_ids),
        "phase_tokens": list(observation.phase_tokens),
        "phases": [
            {
                "name": phase,
                "token": observation.phase_tokens[index],
                "logits": list(observation.phase_logits[index]),
                "cache_leaves": [
                    tensor_record(tensor)
                    for tensor in observation.phase_cache_leaves[index]
                ],
            }
            for index, phase in enumerate(PHASE_NAMES)
        ],
        "readback_schema": READBACK_SCHEMA,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
