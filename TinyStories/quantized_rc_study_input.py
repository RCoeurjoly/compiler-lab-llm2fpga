"""Frozen inputs for the quantized representative-core structural study.

The IDs are an opaque, versioned structural calibration context.  They are not
presented as a language-quality corpus.  Reduced-vocabulary RCs map each full
ID to its first-occurrence class so equality, repetition, ordering, and token
positions remain unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).with_name("quantized_rc_study_input.json")


def load_full_token_ids() -> tuple[int, ...]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported quantized RC study input schema")
    if payload.get("purpose") != "structural-pt2e-calibration":
        raise ValueError("unexpected quantized RC study input purpose")

    context_length = payload.get("context_length")
    token_ids = payload.get("full_token_ids")
    if not isinstance(context_length, int) or context_length != 8:
        raise ValueError("quantized RC study requires exactly eight token positions")
    if not isinstance(token_ids, list) or len(token_ids) != context_length:
        raise ValueError("full_token_ids must contain exactly eight values")
    if not all(isinstance(token_id, int) and token_id >= 0 for token_id in token_ids):
        raise ValueError("full_token_ids must be non-negative integers")
    return tuple(token_ids)


def map_full_token_ids_to_reduced_vocab(
    token_ids: tuple[int, ...], vocab_size: int
) -> tuple[int, ...]:
    """Map IDs by first occurrence without changing equality or position."""

    if vocab_size <= 0:
        raise ValueError("reduced vocabulary must be positive")

    mapping: dict[int, int] = {}
    mapped: list[int] = []
    for token_id in token_ids:
        if token_id not in mapping:
            mapping[token_id] = len(mapping)
        mapped.append(mapping[token_id])

    if len(mapping) > vocab_size:
        raise ValueError(
            "reduced vocabulary cannot represent the frozen token equality classes"
        )
    return tuple(mapped)
