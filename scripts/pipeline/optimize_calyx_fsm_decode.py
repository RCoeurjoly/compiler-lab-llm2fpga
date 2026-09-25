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

STATE_RE = re.compile(r"fsm0_out\s*==\s*(?P<width>\d+)'d(?P<state>\d+)")
# Generated Calyx FSM arms do not nest ternaries inside a condition.  The old
# ``.*?`` expression therefore needlessly rescanned the complete (multi-MB)
# assignment for every arm and could appear to hang forever.  Constrain the
# condition to one arm so matching is linear in the generated assignment.
NEXT_TERM_RE = re.compile(
    r"(?P<cond>[^?]*?)\?\s*(?P<value>(?P<width>\d+)'d\d+)\s*:"
)


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
    state = int(match.group("state"))
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


def _next_state_case(expr: str, state_signal: str) -> str:
    body = expr.split("=", 1)[1].rsplit(";", 1)[0]
    width_match = re.search(r"\b(\d+)'d\d+", body)
    if width_match is None:
        raise ValueError("FSM expression has no sized state literal")
    width = width_match.group(1)
    arms: OrderedDict[int, list[tuple[str, str]]] = OrderedDict()
    cursor = 0
    for match in NEXT_TERM_RE.finditer(body):
        condition = match.group("cond").strip()
        value = match.group("value")
        for term in _split_or(condition):
            state, guard = _state_guard(term)
            arms.setdefault(state, []).append((guard, value))
        cursor = match.end()
    if not arms or not re.search(rf"\b{width}'d0\s*$", body[cursor:].strip()):
        raise ValueError("unexpected fsm0_in chain shape")
    lines = [
        "always_comb begin",
        f"  fsm0_in = {width}'d0;",
        f"  case ({state_signal})",
    ]
    for state, entries in arms.items():
        lines.append(f"    {width}'d{state}: begin")
        for index, (guard, value) in enumerate(entries):
            keyword = "if" if index == 0 else "else if"
            lines.append(f"      {keyword} ({guard}) fsm0_in = {value};")
        lines.append("    end")
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def _write_enable_case(expr: str, state_signal: str) -> str:
    body = expr.split("=", 1)[1].rsplit(";", 1)[0]
    width_match = re.search(r"\b(\d+)'d\d+", body)
    if width_match is None:
        raise ValueError("FSM expression has no sized state literal")
    width = width_match.group(1)
    arms: OrderedDict[int, list[str]] = OrderedDict()
    for term in _split_or(body):
        state, guard = _state_guard(term)
        arms.setdefault(state, []).append(guard)
    if not arms:
        raise ValueError("unexpected fsm0_write_en chain shape")
    lines = [
        "always_comb begin",
        "  fsm0_write_en = 1'b0;",
        f"  case ({state_signal})",
    ]
    for state, guards in arms.items():
        condition = " | ".join(f"({guard})" for guard in guards)
        lines.append(f"    {width}'d{state}: fsm0_write_en = {condition};")
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def _share_state_decodes(source: str, state_signal: str) -> tuple[str, int]:
    state_pattern = rf"{re.escape(state_signal)}\s*==\s*(\d+)'d(\d+)"
    state_matches = re.findall(state_pattern, source)
    matches = sorted({int(value) for _width, value in state_matches})
    if not matches:
        return source, 0
    source = re.sub(
        state_pattern,
        lambda match: f"fsm_state_{match.group(2)}",
        source,
    )
    declarations = "".join(
        f"wire fsm_state_{state} = {state_signal} == {width}'d{state};\n"
        for width, state in state_matches
    )
    declaration_match = re.search(r"logic \[\d+:0\] fsm0_out;", source)
    if declaration_match is None:
        raise ValueError("expected fsm0_out declaration")
    insert_at = declaration_match.end()
    source = source[:insert_at] + "\n" + declarations + source[insert_at:]
    return source, len(matches)


def _hierarchical_state_decodes(source: str, state_signal: str) -> tuple[str, int]:
    state_pattern = rf"{re.escape(state_signal)}\s*==\s*(\d+)'d(\d+)"
    state_matches = re.findall(state_pattern, source)
    matches = sorted({int(value) for _width, value in state_matches})
    if not matches:
        return source, 0
    groups = sorted({state >> 5 for state in matches})
    source = re.sub(
        state_pattern,
        lambda match: (
            f"(fsm_hi_{int(match.group(2)) >> 5} && "
            f"{state_signal}[4:0] == 5'd{int(match.group(2)) & 31})"
        ),
        source,
    )
    width = int(state_matches[0][0])
    high_width = width - 5
    declarations = "".join(
        f"wire fsm_hi_{group} = {state_signal}[{width - 1}:5] == "
        f"{high_width}'d{group};\n"
        for group in groups
    )
    declaration_match = re.search(r"logic \[\d+:0\] fsm0_out;", source)
    if declaration_match is None:
        raise ValueError("expected fsm0_out declaration")
    insert_at = declaration_match.end()
    source = source[:insert_at] + "\n" + declarations + source[insert_at:]
    return source, len(matches)


def transform(source: str, keep_state_copies: bool = False,
              share_state_decodes: bool = False,
              hierarchical_state_decodes: bool = False,
              max_fanout: int | None = None) -> tuple[str, int]:
    next_match = re.search(r"assign\s+fsm0_in\s*=.*?;", source, re.S)
    write_match = re.search(r"assign\s+fsm0_write_en\s*=.*?;", source, re.S)
    if next_match is None or write_match is None:
        raise ValueError("generated SV does not contain both Calyx FSM assignments")
    next_signal = "fsm0_out"
    write_signal = "fsm0_out"
    prefix = ""
    if keep_state_copies:
        declaration_match = re.search(r"logic \[(\d+):0\] fsm0_out;", source)
        if declaration_match is None:
            raise ValueError("expected fsm0_out declaration")
        state_width = int(declaration_match.group(1)) + 1
        prefix = (
            # Keep the named observation points, but let synthesis absorb or
            # replicate the copy wires.  A hard dont_touch barrier forces a
            # physically separate high-fanout network and is therefore not a
            # valid timing experiment for the compiler-generated cone.
            f"(* keep = \"true\" *) wire [{state_width - 1}:0] fsm0_out_decode;\n"
            f"(* keep = \"true\" *) wire [{state_width - 1}:0] fsm0_out_write;\n"
            "assign fsm0_out_decode = fsm0_out;\n"
            "assign fsm0_out_write = fsm0_out;\n"
        )
        next_signal = "fsm0_out_decode"
        write_signal = "fsm0_out_write"
    next_replacement = _next_state_case(next_match.group(0), next_signal)
    write_replacement = _write_enable_case(write_match.group(0), write_signal)
    transformed = _replace_assignment(source, "fsm0_in", next_replacement)
    transformed = _replace_assignment(transformed, "fsm0_write_en", write_replacement)
    if prefix:
        declaration_match = re.search(r"logic \[\d+:0\] fsm0_out;", transformed)
        if declaration_match is None:
            raise ValueError("expected fsm0_out declaration")
        insert_at = declaration_match.end()
        transformed = transformed[:insert_at] + "\n" + prefix + transformed[insert_at:]
    shared_count = 0
    if hierarchical_state_decodes:
        transformed, shared_count = _hierarchical_state_decodes(transformed, next_signal)
    elif share_state_decodes:
        transformed, shared_count = _share_state_decodes(transformed, next_signal)
    if max_fanout is not None:
        if max_fanout < 1:
            raise ValueError("max_fanout must be positive")
        declaration_match = re.search(r"logic \[\d+:0\] fsm0_out;", transformed)
        if declaration_match is None:
            raise ValueError("expected one fsm0_out declaration")
        declaration = declaration_match.group(0)
        transformed = transformed.replace(
            declaration,
            f'(* max_fanout = {max_fanout} *) {declaration}',
            1,
        )
    return transformed, shared_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--keep-state-copies", action="store_true")
    parser.add_argument("--share-state-decodes", action="store_true")
    parser.add_argument("--hierarchical-state-decodes", action="store_true")
    parser.add_argument("--max-fanout", type=int)
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8")
    result, shared_count = transform(
        source,
        keep_state_copies=args.keep_state_copies,
        share_state_decodes=args.share_state_decodes,
        hierarchical_state_decodes=args.hierarchical_state_decodes,
        max_fanout=args.max_fanout,
    )
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
                    "keep_state_copies": args.keep_state_copies,
                    "share_state_decodes": args.share_state_decodes,
                    "hierarchical_state_decodes": args.hierarchical_state_decodes,
                    "max_fanout": args.max_fanout,
                    "shared_state_decode_count": shared_count,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
