#!/usr/bin/env python3
"""Independent, fixed-width LayerNorm model for the authenticated RTL profile.

This is a compiler-side arithmetic primitive, deliberately written from the
Task 3n *receipt* rather than from kev-gpt source or RTL.  It models exactly
one 64-element Q16.16 row, including the documented serial accumulator widths.
It is not evidence that the fixed Python runtime has the same full-domain
semantics, nor that this primitive has reached hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence


WIDTH = 64
EPSILON_Q32 = 42950
RECEIPT_SHA256 = "44bdd11a2e52831006c1eca6345916f248b94797d9fd2020c7b1f150530a0278"


class RtlLayerNormError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _wrap_unsigned(value: int, width: int) -> int:
    return value & ((1 << width) - 1)


def _wrap_signed(value: int, width: int) -> int:
    unsigned = _wrap_unsigned(value, width)
    return unsigned - (1 << width) if unsigned & (1 << (width - 1)) else unsigned


def _trunc_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise RtlLayerNormError("invalid_denominator", str(denominator))
    quotient = abs(numerator) // denominator
    return -quotient if numerator < 0 else quotient


def _q16_vector(values: Sequence[int], label: str) -> list[int]:
    if len(values) != WIDTH:
        raise RtlLayerNormError("shape_mismatch", f"{label} must have exactly {WIDTH} elements")
    result: list[int] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, int):
            raise RtlLayerNormError("invalid_q16_value", f"{label}[{index}] must be an integer")
        if not -(1 << 31) <= value < (1 << 31):
            raise RtlLayerNormError("q16_port_overflow", f"{label}[{index}] is outside signed 32-bit range")
        result.append(value)
    return result


def affine_rtl(normalized_q16_16: Sequence[int], gamma_q16_16: Sequence[int], beta_q16_16: Sequence[int]) -> list[int]:
    """RTL affine tail: Q16.16 product, arithmetic shift, add, signed-32 wrap."""
    lengths = {len(normalized_q16_16), len(gamma_q16_16), len(beta_q16_16)}
    if len(lengths) != 1:
        raise RtlLayerNormError("shape_mismatch", "normalized, gamma, and beta must have equal lengths")
    def checked(values: Sequence[int], label: str) -> list[int]:
        result: list[int] = []
        for index, value in enumerate(values):
            if isinstance(value, bool) or not isinstance(value, int):
                raise RtlLayerNormError("invalid_q16_value", f"{label}[{index}] must be an integer")
            if not -(1 << 31) <= value < (1 << 31):
                raise RtlLayerNormError("q16_port_overflow", f"{label}[{index}] is outside signed 32-bit range")
            result.append(value)
        return result
    normalized = checked(normalized_q16_16, "normalized")
    gamma = checked(gamma_q16_16, "gamma")
    beta = checked(beta_q16_16, "beta")
    return [_wrap_signed(((value * scale) >> 16) + offset, 32) for value, scale, offset in zip(normalized, gamma, beta)]


def fixed_layer_norm_rtl(
    values_q16_16: Sequence[int], gamma_q16_16: Sequence[int], beta_q16_16: Sequence[int], *, details: bool = False
) -> list[int] | dict[str, Any]:
    """Execute the receipt-defined RTL-width LayerNorm operation."""
    values = _q16_vector(values_q16_16, "values")
    gamma = _q16_vector(gamma_q16_16, "gamma")
    beta = _q16_vector(beta_q16_16, "beta")
    mean_accumulator_64 = _wrap_signed(sum(values), 64)
    mean = _trunc_div(mean_accumulator_64, WIDTH)
    deltas_33 = [_wrap_signed(value - mean, 33) for value in values]
    squares_66 = [_wrap_unsigned(delta * delta, 66) for delta in deltas_33]
    square_sum_72 = 0
    for square in squares_66:
        square_sum_72 = _wrap_unsigned(square_sum_72 + square, 72)
    variance_u64 = _wrap_unsigned((square_sum_72 // WIDTH) + EPSILON_Q32, 64)
    deviation = math.isqrt(variance_u64)
    if deviation == 0:
        raise RtlLayerNormError("zero_deviation", "epsilon and declared widths produced zero divisor")
    normalized = [_wrap_signed(_trunc_div(delta << 16, deviation), 32) for delta in deltas_33]
    output = [_wrap_signed(((value * scale) >> 16) + offset, 32) for value, scale, offset in zip(normalized, gamma, beta)]
    if not details:
        return output
    return {
        "mean_q16_16": mean,
        "square_sum_72": square_sum_72,
        "variance_u64": variance_u64,
        "deviation_floor_sqrt": deviation,
        "normalized_q16_16": normalized,
        "output_q16_16": output,
    }


def compiler_integration_status() -> dict[str, Any]:
    """Truthful post-Task-3p state; no backend/board equivalence is implied."""
    return {
        "status": "unsupported",
        "bridge_status": "custom_op_emitted",
        "code": "fixed_layer_norm_backend_lowering_not_implemented",
        "reason": (
            "the authenticated package export is bridged to an inspectable "
            "llm2fpga custom op, but the current Linalg/Calyx backend has no legalization for it"
        ),
        "runtime_equivalent": False,
        "board_authenticated": False,
        "next_unsupported_operation": "llm2fpga.fixed_layer_norm_q16_16",
    }


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def vector_sha256(vector: dict[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in vector.items() if key != "sha256"})


def generated_vector() -> dict[str, Any]:
    values = [65536 if index % 2 == 0 else -65536 for index in range(WIDTH)]
    gamma = [65536] * WIDTH
    beta = [0] * WIDTH
    vector = {
        "schema": "tinystories-1m-rtl-layernorm-vector-v1",
        "profile": "synthesizable_rtl",
        "layernorm_receipt_sha256": RECEIPT_SHA256,
        "input_q16_16": values,
        "gamma_q16_16": gamma,
        "beta_q16_16": beta,
        "result": fixed_layer_norm_rtl(values, gamma, beta, details=True),
    }
    vector["sha256"] = vector_sha256(vector)
    return vector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(generated_vector(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
