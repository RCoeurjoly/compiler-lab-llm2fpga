#!/usr/bin/env python3
"""Independent two's-complement oracle for scalar i64 math.absi lowering."""

from __future__ import annotations

import json
import random


MASK = (1 << 64) - 1
SIGN_BIT = 1 << 63


def lowered_absi_bits(bits: int) -> int:
    """Evaluate the sign-mask lowering on an unsigned 64-bit encoding."""
    if not 0 <= bits <= MASK:
        raise ValueError("bits must be an unsigned 64-bit pattern")
    sign = MASK if bits & SIGN_BIT else 0
    return ((bits ^ sign) - sign) & MASK


def expected_absi_bits(bits: int) -> int:
    """Evaluate signed i64 absolute value as a wrapped 64-bit encoding."""
    if not 0 <= bits <= MASK:
        raise ValueError("bits must be an unsigned 64-bit pattern")
    sign = MASK if bits & SIGN_BIT else 0
    return bits if sign == 0 else (-bits) & MASK


def contract_patterns() -> list[tuple[str, int]]:
    patterns = [
        ("zero", 0),
        ("positive-one", 1),
        ("negative-one", MASK),
        ("i64-max", SIGN_BIT - 1),
        ("i64-max-minus-one", SIGN_BIT - 2),
        ("i64-min", SIGN_BIT),
        ("i64-min-plus-one", SIGN_BIT + 1),
        ("two-to-the-31", 1 << 31),
        ("negative-two-to-the-31", MASK - (1 << 31) + 1),
        ("two-to-the-62", 1 << 62),
        ("negative-two-to-the-62", MASK - (1 << 62) + 1),
        ("alternating-01", 0x5555555555555555),
        ("alternating-10", 0xAAAAAAAAAAAAAAAA),
    ]
    generator = random.Random(0x49363441425349)
    patterns.extend(
        (f"random-{index:03d}", generator.getrandbits(64))
        for index in range(128)
    )
    return patterns


def main() -> None:
    report = []
    for label, bits in contract_patterns():
        lowered = lowered_absi_bits(bits)
        expected = expected_absi_bits(bits)
        assert lowered == expected
        report.append(
            {
                "label": label,
                "input": f"0x{bits:016X}",
                "expected": f"0x{expected:016X}",
                "lowered": f"0x{lowered:016X}",
            }
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
