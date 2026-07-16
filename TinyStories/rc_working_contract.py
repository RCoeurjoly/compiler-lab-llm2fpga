"""Stable inputs and result schema for the quantized TinyStories working RC."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any


RC_WORKING_SOURCE_MODEL_KEY = "tinystories-w8a8-rc-study-mask9-vocab6-width2"
RC_WORKING_PIPELINE_ALIAS = "tinystories-w8a8-rc-working-via-linalg-no-handshake"
CONTEXT_LENGTH = 8
VOCAB_SIZE = 6
SCHEMA_VERSION = 1
VOCABULARY = tuple(f"tok{index}" for index in range(VOCAB_SIZE))


def _validate_token_ids(token_ids: Sequence[int]) -> list[int]:
    if isinstance(token_ids, (str, bytes)) or len(token_ids) != CONTEXT_LENGTH:
        raise ValueError(f"expected exactly {CONTEXT_LENGTH} token IDs")

    normalized = list(token_ids)
    if not all(
        isinstance(token_id, int)
        and not isinstance(token_id, bool)
        and 0 <= token_id < VOCAB_SIZE
        for token_id in normalized
    ):
        raise ValueError(f"token IDs must be integers in [0, {VOCAB_SIZE})")
    return normalized


def tokenize(text: str) -> list[int]:
    """Map the fixed whitespace-token ABI to the six working-RC token IDs."""

    if not isinstance(text, str):
        raise ValueError("prompt must be a string")
    tokens = text.split()
    if len(tokens) != CONTEXT_LENGTH:
        raise ValueError(f"expected exactly {CONTEXT_LENGTH} whitespace-separated tokens")

    token_ids: list[int] = []
    for token in tokens:
        if token not in VOCABULARY:
            raise ValueError(f"unsupported working-RC token: {token!r}")
        token_ids.append(int(token.removeprefix("tok")))
    return token_ids


def decode_token_ids(token_ids: Sequence[int]) -> str:
    """Return the canonical textual form of a fixed working-RC input."""

    return " ".join(f"tok{token_id}" for token_id in _validate_token_ids(token_ids))


def load_corpus(path: str | Path) -> list[dict[str, str]]:
    """Load and validate the immutable four-case working-RC corpus."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported working-RC corpus schema")
    if payload.get("context_length") != CONTEXT_LENGTH:
        raise ValueError("working-RC corpus must use eight input positions")
    if payload.get("vocabulary") != list(VOCABULARY):
        raise ValueError("working-RC corpus vocabulary does not match the fixed ABI")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 4:
        raise ValueError("working-RC corpus must contain exactly four cases")

    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("working-RC corpus case must be an object")
        case_id = case.get("id")
        text = case.get("text")
        if not isinstance(case_id, str) or not case_id or case_id in seen_ids:
            raise ValueError("working-RC corpus case IDs must be unique non-empty strings")
        if not isinstance(text, str):
            raise ValueError("working-RC corpus case text must be a string")
        tokenize(text)
        seen_ids.add(case_id)
        normalized.append({"id": case_id, "text": text})
    return normalized


def validate_output_qparams(scale: float, zero_point: int) -> None:
    if (
        isinstance(scale, bool)
        or not isinstance(scale, (int, float))
        or not math.isfinite(float(scale))
        or float(scale) <= 0.0
    ):
        raise ValueError("output scale must be finite and positive")
    if not isinstance(zero_point, int) or isinstance(zero_point, bool):
        raise ValueError("output zero_point must be an integer")


def validate_output_tensor(tensor: Any) -> None:
    """Validate the fixed [1, 8, 6] raw-code output shape."""

    try:
        shape = tuple(int(dimension) for dimension in tensor.shape)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("output tensor must expose a static shape") from error
    if shape != (1, CONTEXT_LENGTH, VOCAB_SIZE):
        raise ValueError(
            "expected output tensor shape "
            f"(1, {CONTEXT_LENGTH}, {VOCAB_SIZE}), got {shape}"
        )


def _validate_codes(codes: Sequence[int]) -> list[int]:
    if isinstance(codes, (str, bytes)) or len(codes) != VOCAB_SIZE:
        raise ValueError(f"expected exactly {VOCAB_SIZE} int8 output codes")
    normalized = list(codes)
    if not all(
        isinstance(code, int)
        and not isinstance(code, bool)
        and -128 <= code <= 127
        for code in normalized
    ):
        raise ValueError("output codes must be signed int8 values")
    return normalized


def argmax_lowest(values: Sequence[int]) -> int:
    """Choose the largest logit code, resolving ties toward the lower token ID."""

    codes = _validate_codes(values)
    return max(range(VOCAB_SIZE), key=lambda index: (codes[index], -index))


def canonical_result(
    *,
    case_id: str,
    token_ids: Sequence[int],
    output_codes_i8: Sequence[int],
    output_scale: float,
    output_zero_point: int,
) -> dict[str, object]:
    """Build the common oracle/result record for one fixed prompt case."""

    if not isinstance(case_id, str) or not case_id:
        raise ValueError("case_id must be a non-empty string")
    normalized_ids = _validate_token_ids(token_ids)
    codes = _validate_codes(output_codes_i8)
    validate_output_qparams(output_scale, output_zero_point)
    scale = float(output_scale)

    return {
        "schema_version": SCHEMA_VERSION,
        "source_model_key": RC_WORKING_SOURCE_MODEL_KEY,
        "pipeline_alias": RC_WORKING_PIPELINE_ALIAS,
        "case_id": case_id,
        "token_ids": normalized_ids,
        "output_qparams": {"scale": scale, "zero_point": output_zero_point},
        "output_codes_i8": codes,
        "logits": [scale * (code - output_zero_point) for code in codes],
        "token_id": argmax_lowest(codes),
    }
