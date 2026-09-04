"""Frozen arithmetic and artifact contract for the W4A8 serving RC."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence


W4A8_MODEL_KEY = "tinystories-w4a8-rc-serving-mask10-vocab6-width2"
WEIGHT_BITS, WEIGHT_MIN, WEIGHT_MAX = 4, -8, 7
ACTIVATION_BITS, ACTIVATION_MIN, ACTIVATION_MAX = 8, -128, 127
NIBBLE_ORDER = "low-even-high-odd"
PADDING_MODE = "zero-high-nibble"
ROUNDING_MODE = "round-to-nearest-even"
SATURATION_MODE = "signed-clamp"
PHASE_NAMES = ("prefill-8", "decode-8", "decode-9")
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class QuantizedTensorRecord:
    name: str
    shape: tuple[int, ...]
    bits: int
    signed: bool
    element_count: int
    packed_byte_count: int
    sha256: str


@dataclass(frozen=True)
class W4A8Manifest:
    schema_version: int
    model_key: str
    tensors: tuple[QuantizedTensorRecord, ...]


def accumulator_bounds(reduction_length: int) -> tuple[int, int]:
    if reduction_length <= 0:
        raise ValueError("reduction_length must be positive")
    products = (
        WEIGHT_MIN * ACTIVATION_MAX,
        WEIGHT_MIN * ACTIVATION_MIN,
        WEIGHT_MAX * ACTIVATION_MAX,
        WEIGHT_MAX * ACTIVATION_MIN,
    )
    return reduction_length * min(products), reduction_length * max(products)


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _require_exact(mapping: Mapping[str, object], field: str, expected: object) -> None:
    if mapping.get(field) != expected:
        raise ValueError(f"{field} must equal {expected!r}")


def _parse_tensor(value: object) -> QuantizedTensorRecord:
    raw = _require_mapping(value, "tensor")
    name = raw.get("name")
    shape = raw.get("shape")
    if not isinstance(name, str) or not name:
        raise ValueError("tensor name must be nonempty")
    if not isinstance(shape, Sequence) or isinstance(shape, (str, bytes)):
        raise ValueError(f"tensor {name} shape must be an array")
    dimensions = tuple(shape)
    if not dimensions or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in dimensions):
        raise ValueError(f"tensor {name} shape dimensions must be positive integers")
    element_count = 1
    for dimension in dimensions:
        element_count *= dimension
    _require_exact(raw, "bits", WEIGHT_BITS)
    _require_exact(raw, "signed", True)
    _require_exact(raw, "element_count", element_count)
    packed_byte_count = (element_count + 1) // 2
    _require_exact(raw, "packed_byte_count", packed_byte_count)
    digest = raw.get("sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise ValueError(f"tensor {name} sha256 must be lowercase hexadecimal")
    return QuantizedTensorRecord(
        name, dimensions, WEIGHT_BITS, True, element_count, packed_byte_count, digest
    )


def validate_manifest(payload: object) -> W4A8Manifest:
    raw = _require_mapping(payload, "manifest")
    _require_exact(raw, "schema_version", 1)
    _require_exact(raw, "model_key", W4A8_MODEL_KEY)

    quantization = _require_mapping(raw.get("quantization"), "quantization")
    weights = _require_mapping(quantization.get("weights"), "weights")
    activations = _require_mapping(quantization.get("activations"), "activations")
    for mapping, values in (
        (weights, (WEIGHT_BITS, WEIGHT_MIN, WEIGHT_MAX)),
        (activations, (ACTIVATION_BITS, ACTIVATION_MIN, ACTIVATION_MAX)),
    ):
        _require_exact(mapping, "bits", values[0])
        _require_exact(mapping, "signed", True)
        _require_exact(mapping, "minimum", values[1])
        _require_exact(mapping, "maximum", values[2])
    _require_exact(quantization, "rounding", ROUNDING_MODE)
    _require_exact(quantization, "saturation", SATURATION_MODE)

    packing = _require_mapping(raw.get("packing"), "packing")
    _require_exact(packing, "nibble_order", NIBBLE_ORDER)
    _require_exact(packing, "padding", PADDING_MODE)
    if raw.get("phases") != list(PHASE_NAMES):
        raise ValueError("phases must be in canonical order")

    tensor_values = raw.get("tensors")
    if not isinstance(tensor_values, list) or not tensor_values:
        raise ValueError("tensors must be a nonempty array")
    tensors = tuple(_parse_tensor(value) for value in tensor_values)
    if len({tensor.name for tensor in tensors}) != len(tensors):
        raise ValueError("tensor names must be unique")
    return W4A8Manifest(1, W4A8_MODEL_KEY, tensors)
