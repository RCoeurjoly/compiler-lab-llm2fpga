#!/usr/bin/env python3
"""Promote a single invoked Calyx component to the toplevel.

The no-handshake RC export can contain a synthetic ``main`` component whose
only operation is invoking the real ``main_1`` component.  Flat Verilog
emission preserves that invocation as a wrapper with a liveness bug.  This
transform removes only that wrapper and marks the invoked component as the
toplevel, preserving the invoked component's ref-memory ABI and schedule.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def _component_ranges(source: str) -> list[tuple[str, int, int]]:
    matches = list(re.finditer(r"(?m)^component\s+([A-Za-z_][A-Za-z0-9_]*)\b", source))
    ranges: list[tuple[str, int, int]] = []
    for match in matches:
        opening = source.find("{", match.end())
        if opening < 0:
            raise ValueError(f"component {match.group(1)} has no body")
        depth = 0
        closing = -1
        for index in range(opening, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    closing = index + 1
                    break
        if closing < 0:
            raise ValueError(f"component {match.group(1)} has an unterminated body")
        ranges.append((match.group(1), match.start(), closing))
    return ranges


def promote(source: str) -> str:
    components = _component_ranges(source)
    if len(components) != 2 or components[0][0] != "main" or components[1][0] != "main_1":
        raise ValueError("expected exactly main followed by main_1 components")
    main_start, main_end = components[0][1], components[0][2]
    main = source[main_start:main_end]
    invokes = re.findall(r"\binvoke\s+main_1_instance\s*\[.*?\]\s*\(\)\(\);", main, flags=re.DOTALL)
    if len(invokes) != 1:
        raise ValueError("main is not a single invoke of main_1_instance")
    inner_start, inner_end = components[1][1], components[1][2]
    inner = source[inner_start:inner_end]
    if '"toplevel"' in inner:
        raise ValueError("main_1 already has a toplevel attribute")
    inner = re.sub(r"^component\s+main_1\(", 'component main_1<"toplevel"=1,>(', inner, count=1, flags=re.MULTILINE)
    if inner == source[inner_start:inner_end]:
        raise ValueError("failed to add main_1 toplevel attribute")
    return source[:main_start] + inner + source[main_end:inner_start] + source[inner_end:]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = promote(args.input.read_text(encoding="utf-8"))
    args.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
