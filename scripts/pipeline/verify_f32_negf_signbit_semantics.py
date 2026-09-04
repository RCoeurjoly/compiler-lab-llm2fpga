#!/usr/bin/env python3
"""Independent binary32 bit-pattern oracle for scalar arith.negf lowering."""

from __future__ import annotations

import json
import random


SIGN_MASK = 0x80000000
UINT32_MASK = 0xFFFFFFFF


def expected_negf_bits(bits: int) -> int:
    """Return IEEE binary32 negation by toggling exactly the sign bit."""
    if not 0 <= bits <= UINT32_MASK:
        raise ValueError("bits must be an unsigned 32-bit pattern")
    return bits ^ SIGN_MASK


def contract_patterns() -> list[tuple[str, int]]:
    patterns = [
        ("positive-zero", 0x00000000),
        ("negative-zero", 0x80000000),
        ("positive-normal", 0x3FC00000),
        ("negative-normal", 0xC0200000),
        ("positive-smallest-subnormal", 0x00000001),
        ("negative-largest-subnormal", 0x807FFFFF),
        ("positive-infinity", 0x7F800000),
        ("negative-infinity", 0xFF800000),
        ("positive-qnan-payload", 0x7FC12345),
        ("negative-qnan-payload", 0xFFC54321),
        ("positive-snan-payload", 0x7F812345),
        ("negative-snan-payload", 0xFF812345),
    ]
    generator = random.Random(0x4E454746)
    patterns.extend(
        (f"random-{index:03d}", generator.getrandbits(32))
        for index in range(128)
    )
    return patterns


def main() -> None:
    print(
        json.dumps(
            [
                {"label": label, "input": f"0x{bits:08X}",
                 "expected": f"0x{expected_negf_bits(bits):08X}"}
                for label, bits in contract_patterns()
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
