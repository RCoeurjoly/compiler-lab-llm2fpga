#!/usr/bin/env python3
"""Independent binary64 contract oracle for the fused floor-to-i64 lowering."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass


I64_MIN = -(2**63)
I64_MAX = 2**63 - 1


@dataclass(frozen=True)
class CaseResult:
    label: str
    classification: str
    expected: int | None
    lowered: int | None


def in_original_defined_domain(value: float) -> bool:
    """Whether floor(value) is finite and representable as a signed i64."""
    if not math.isfinite(value):
        return False
    floor_value = math.floor(value)
    return I64_MIN <= floor_value <= I64_MAX


def floor_to_i64(value: float) -> int:
    """Check the lowering equation independently on the original defined domain."""
    if not in_original_defined_domain(value):
        raise ValueError("outside original fptosi-to-i64 defined domain")

    trunc = math.trunc(value)
    lowered = trunc - 1 if value < float(trunc) else trunc
    expected = math.floor(value)
    assert lowered == expected
    return lowered


def classify(label: str, value: float) -> CaseResult:
    if not in_original_defined_domain(value):
        return CaseResult(label, "outside-original-defined-domain", None, None)
    lowered = floor_to_i64(value)
    return CaseResult(label, "defined", math.floor(value), lowered)


def contract_cases() -> list[tuple[str, float]]:
    two52 = float(2**52)
    two53 = float(2**53)
    positive_i64_edge = math.nextafter(float(2**63), -math.inf)
    return [
        ("positive-fraction", 1.5),
        ("negative-fraction", -1.5),
        ("positive-integer", 17.0),
        ("negative-integer", -17.0),
        ("negative-zero", -0.0),
        ("nextafter-positive-integer-down", math.nextafter(17.0, -math.inf)),
        ("nextafter-negative-integer-up", math.nextafter(-17.0, math.inf)),
        ("two52", two52),
        ("two52-next-down", math.nextafter(two52, -math.inf)),
        ("two52-next-up", math.nextafter(two52, math.inf)),
        ("two53", two53),
        ("two53-next-down", math.nextafter(two53, -math.inf)),
        ("two53-next-up", math.nextafter(two53, math.inf)),
        ("i64-min", float(I64_MIN)),
        ("i64-max-representable-neighbor", positive_i64_edge),
        ("i64-max-outside", float(2**63)),
        ("i64-min-next-down-outside", math.nextafter(float(I64_MIN), -math.inf)),
        ("nan", math.nan),
        ("positive-infinity", math.inf),
        ("negative-infinity", -math.inf),
    ]


def main() -> None:
    print(
        json.dumps(
            [asdict(classify(label, value)) for label, value in contract_cases()],
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
