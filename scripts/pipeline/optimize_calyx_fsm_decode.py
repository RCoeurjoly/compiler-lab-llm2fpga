#!/usr/bin/env python3
"""Factor Calyx's flat schedule-FSM decode into per-state case arms.

Calyx's Verilog backend emits the next-state and write-enable expressions as
large chains of repeated ``fsm0_out == state`` tests.  This pass is deliberately
limited to that generated shape: it does not change state values or guards; it
only factors the common state comparison into a case statement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path

STATE_RE = re.compile(r"fsm0_out\s*==\s*11'd(\d+)")
NEXT_TERM_RE = re.compile(r"(?P<cond>.*?)\?\s*(?P<value>11'd\d+)\s*:", re.S)


def _split_or(expr: str) -> list[str]:
    # The generated guards contain no parenthesized OR expressions; retain a
    # conservative splitter so this pass refuses unexpected nested syntax.
    if "(" in expr or ")" in expr:
        depth = 0
        pieces: list[str] = []
        start = 0
        for i, char in enumerate(expr):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "|" and depth == 0:
                pieces.append(expr[start:i])
                start = i + 1
        pieces.append(expr[start:])
        return pieces
    return re.split(r"\s*\|\s*", expr)


def _state_guard(term: str) -> tuple[int, str]:
    match = STATE_RE.search(term)
    if match is None:
        raise ValueError(f"FSM term has no state comparison: {term[:120]!r}")
    state = int(match.group(1))
    guard = (term[: match.start()] + term[match.end() :]).strip()
    guard = re.sub(r"^\s*&\s*", "", guard)
    return state, guard or "1'b1"


def _replace_assignment(source: str, name: str, replacement: str) -> str:
    pattern = re.compile(rf"assign\s+{re.escape(name)}\s*=.*?;", re.S)
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected one assignment for {name}, found {len(matches)}")
    match = matches[0]
    return source[: match.start()] + replacement + source[match.end() :]


def _next_state_case(expr: str) -> str:
    body = expr.split("=", 1)[1].rsplit(";", 1)[0]
    arms: OrderedDict[int, list[tuple[str, str]]] = OrderedDict()
    cursor = 0
    for match in NEXT_TERM_RE.finditer(body):
        condition = match.group("cond").strip()
        value = match.group("value")
        for term in _split_or(condition):
            state, guard = _state_guard(term)
            arms.setdefault(state, []).append((guard, value))
        cursor = match.end()
    if not arms or "11'd0" not in body[cursor:]:
        raise ValueError("unexpected fsm0_in chain shape")
    lines = ["always_comb begin", "  fsm0_in = 11'd0;", "  case (fsm0_out)"]
    for state, entries in arms.items():
        lines.append(f"    11'd{state}: begin")
        for index, (guard, value) in enumerate(entries):
            keyword = "if" if index == 0 else "else if"
            lines.append(f"      {keyword} ({guard}) fsm0_in = {value};")
        lines.append("    end")
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def _write_enable_case(expr: str) -> str:
    body = expr.split("=", 1)[1].rsplit(";", 1)[0]
    arms: OrderedDict[int, list[str]] = OrderedDict()
    for term in _split_or(body):
        state, guard = _state_guard(term)
        arms.setdefault(state, []).append(guard)
    if not arms:
        raise ValueError("unexpected fsm0_write_en chain shape")
    lines = ["always_comb begin", "  fsm0_write_en = 1'b0;", "  case (fsm0_out)"]
    for state, guards in arms.items():
        condition = " | ".join(f"({guard})" for guard in guards)
        lines.append(f"    11'd{state}: fsm0_write_en = {condition};")
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def transform(source: str) -> str:
    next_match = re.search(r"assign\s+fsm0_in\s*=.*?;", source, re.S)
    write_match = re.search(r"assign\s+fsm0_write_en\s*=.*?;", source, re.S)
    if next_match is None or write_match is None:
        raise ValueError("generated SV does not contain both Calyx FSM assignments")
    next_replacement = _next_state_case(next_match.group(0))
    write_replacement = _write_enable_case(write_match.group(0))
    transformed = _replace_assignment(source, "fsm0_in", next_replacement)
    return _replace_assignment(transformed, "fsm0_write_en", write_replacement)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8")
    result = transform(source)
    args.output.write_text(result, encoding="utf-8")
    if args.receipt is not None:
        args.receipt.write_text(
            json.dumps(
                {
                    "schema": "llm2fpga.calyx-fsm-decode.v1",
                    "status": "ok",
                    "input_sv_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "output_sv_sha256": hashlib.sha256(result.encode()).hexdigest(),
                    "state_logic": "fsm0_in and fsm0_write_en",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
