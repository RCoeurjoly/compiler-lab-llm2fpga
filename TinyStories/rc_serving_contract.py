"""Frozen contract for the stateful TinyStories serving representative core."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


SERVING_RC_MODEL_KEY = "tinystories-w8a8-rc-serving-mask10-vocab6-width2"
VOCAB_SIZE = 6
NUM_LAYERS = 2
MAX_POSITION_EMBEDDINGS = 10
WINDOW_SIZE = 256
HIDDEN_SIZE = 2
NUM_HEADS = 1
PREFILL_LENGTH = 8
DECODE_STEPS = 2
TRACE_SCHEMA_VERSION = 1
TRACE_PURPOSE = "stateful-serving-native-cache-trace"
PHASE_NAMES = ("prefill-8", "decode-8", "decode-9")


@dataclass(frozen=True)
class ServingPhase:
    name: str
    input_length: int
    cache_length_before: int
    cache_length_after: int
    cache_positions: tuple[int, ...]


@dataclass(frozen=True)
class ServingTrace:
    prompt_token_ids: tuple[int, ...]
    phases: tuple[ServingPhase, ...]


def validate_token_ids(values: Sequence[int], expected_length: int) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)) or len(values) != expected_length:
        raise ValueError(f"expected exactly {expected_length} token IDs")
    normalized = tuple(values)
    if not all(
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value < VOCAB_SIZE
        for value in normalized
    ):
        raise ValueError(f"token IDs must be integers in range [0, {VOCAB_SIZE})")
    return normalized


def argmax_lowest(values: Sequence[float]) -> int:
    if isinstance(values, (str, bytes)) or len(values) != VOCAB_SIZE:
        raise ValueError("expected exactly 6 logits")
    normalized = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in normalized):
        raise ValueError("logits must be finite")
    return max(range(VOCAB_SIZE), key=lambda index: (normalized[index], -index))


def phase_by_name(name: str) -> ServingPhase:
    phases = {
        "prefill-8": ServingPhase(
            "prefill-8", 8, 0, 8, (0, 1, 2, 3, 4, 5, 6, 7)
        ),
        "decode-8": ServingPhase("decode-8", 1, 8, 9, (8,)),
        "decode-9": ServingPhase("decode-9", 1, 9, 10, (9,)),
    }
    try:
        return phases[name]
    except KeyError as error:
        raise ValueError(f"unknown serving phase: {name!r}") from error


def _validate_phase(raw: object, expected: ServingPhase) -> ServingPhase:
    if not isinstance(raw, dict):
        raise ValueError("serving trace phase must be an object")
    if raw.get("name") != expected.name:
        raise ValueError(f"unexpected phase name for {expected.name}")
    if raw.get("input_length") != expected.input_length:
        raise ValueError(f"{expected.name} input length is not fixed")
    if raw.get("cache_length_before") != expected.cache_length_before:
        raise ValueError(f"{expected.name} cache input length is not fixed")
    if raw.get("cache_length_after") != expected.cache_length_after:
        raise ValueError(f"{expected.name} cache output length is not fixed")
    positions = raw.get("cache_positions")
    if tuple(positions or ()) != expected.cache_positions:
        raise ValueError(f"{expected.name} cache positions are not fixed")
    return expected


def load_trace(path: str | Path) -> ServingTrace:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("serving trace must be a JSON object")
    if payload.get("schema_version") != TRACE_SCHEMA_VERSION:
        raise ValueError("unsupported serving trace schema")
    if payload.get("model_key") != SERVING_RC_MODEL_KEY:
        raise ValueError("serving trace model key does not match")
    if payload.get("purpose") != TRACE_PURPOSE:
        raise ValueError("unexpected serving trace purpose")

    prompt = validate_token_ids(payload.get("prompt_token_ids", ()), PREFILL_LENGTH)
    raw_phases = payload.get("phases")
    if not isinstance(raw_phases, list) or len(raw_phases) != len(PHASE_NAMES):
        raise ValueError("serving trace must contain exactly three phases")
    phases = tuple(
        _validate_phase(raw_phase, phase_by_name(name))
        for raw_phase, name in zip(raw_phases, PHASE_NAMES)
    )
    return ServingTrace(prompt_token_ids=prompt, phases=phases)
