#!/usr/bin/env python3
"""Remove complementary FSM guards from compiler-generated write enables.

Calyx emits pairs such as ``fsm_out != 3'd3 & signal | fsm_out == 3'd3 &
signal``.  The guards are complementary, so the pair is exactly ``signal``.
Leaving the redundant pair intact creates very deep Yosys/Verilator expression
trees without changing behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ASSIGNMENT = re.compile(r"(?ms)(?P<prefix>\bassign\s+fsm_write_en\s*=\s*)(?P<body>.*?)(?P<suffix>;)")
ANY_ASSIGNMENT = re.compile(r"(?ms)(?P<prefix>\bassign\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*)(?P<body>.*?)(?P<suffix>;)")
def _pair_pattern(operator: str) -> re.Pattern[str]:
    first = "!=" if operator == "eq_ne" else "=="
    second = "==" if operator == "eq_ne" else "!="
    return re.compile(
        rf"fsm_out\s*{first}\s*(?P<literal>\d+'[dDhHbBoO][0-9a-fA-FxXzZ]+)"
        rf"\s*&\s*(?P<signal>[A-Za-z_$][A-Za-z0-9_$]*)\s*\|\s*"
        rf"fsm_out\s*{second}\s*(?P=literal)\s*&\s*(?P=signal)"
    )


PAIR_PATTERNS = (_pair_pattern("eq_ne"), _pair_pattern("ne_eq"))


def simplify(source: str) -> tuple[str, int]:
    matches = list(ASSIGNMENT.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one fsm_write_en assignment, found {len(matches)}")
    match = matches[0]
    body = match.group("body")
    replacements = 0
    while True:
        changed = False
        for pattern in PAIR_PATTERNS:
            body, count = pattern.subn(lambda m: m.group("signal"), body)
            replacements += count
            changed |= count > 0
        if not changed:
            break
    terms = [term.strip() for term in body.split("|") if term.strip()]
    if len(terms) > 2 and "?" not in body and "||" not in body:
        level = terms
        while len(level) > 1:
            level = [
                f"({level[index]} | {level[index + 1]})"
                if index + 1 < len(level) else level[index]
                for index in range(0, len(level), 2)
            ]
        body = "\n  " + level[0].replace(" | ", " |\n  ")
    output = source[:match.start("body")] + body + source[match.end("body"):]
    return output, replacements


def balance_large_assignments(source: str, *, minimum_bytes: int = 10_000) -> tuple[str, int]:
    """Balance long pure-OR continuous assignments without changing terms."""

    balanced = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal balanced
        body = match.group("body")
        if len(match.group(0)) < minimum_bytes or "?" in body or "||" in body:
            return match.group(0)
        terms = [term.strip() for term in body.split("|") if term.strip()]
        if len(terms) <= 2:
            return match.group(0)
        level = terms
        while len(level) > 1:
            level = [
                f"({level[index]} | {level[index + 1]})"
                if index + 1 < len(level) else level[index]
                for index in range(0, len(level), 2)
            ]
        balanced += 1
        return match.group("prefix") + "\n  " + level[0].replace(" | ", " |\n  ") + match.group("suffix")

    return ANY_ASSIGNMENT.sub(replace, source), balanced


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <input.sv> <output.sv> <receipt.json>", file=sys.stderr)
        return 2
    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    output, replacements = simplify(source)
    output, balanced_assignments = balance_large_assignments(output)
    Path(sys.argv[2]).write_text(output, encoding="utf-8")
    Path(sys.argv[3]).write_text(json.dumps({
        "schema": "llm2fpga.fsm-guarded-or-simplification.v1",
        "input_sv_sha256": sha256(source),
        "output_sv_sha256": sha256(output),
        "replacement_count": replacements,
        "balanced_assignment_count": balanced_assignments,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"replaced {replacements} complementary FSM guard pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
