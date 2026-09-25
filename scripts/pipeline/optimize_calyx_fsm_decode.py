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
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        encloses_all = True
        for index, char in enumerate(expr):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(expr) - 1:
                    encloses_all = False
                    break
        if not encloses_all or depth != 0:
            break
        expr = expr[1:-1].strip()
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


def _expand_guard_aliases(
    term: str, aliases: dict[str, str], cache: dict[str, str]
) -> str:
    """Resolve Calyx's wire guard aliases without expanding unrelated logic."""
    key = term.strip()
    if key in cache:
        return cache[key]
    result = key
    for _ in range(64):
        changed = False

        def replace(match: re.Match[str]) -> str:
            nonlocal changed
            name = match.group(0)
            value = aliases.get(name)
            if value is None:
                return name
            changed = True
            return f"({value})"

        expanded = re.sub(r"\b_guard\d+\b", replace, result)
        result = expanded
        if not changed:
            break
    cache[key] = result
    return result


def _state_guard(
    term: str, state_signal: str, aliases: dict[str, str], cache: dict[str, str]
) -> tuple[int, str]:
    term = _expand_guard_aliases(term, aliases, cache)
    state_re = re.compile(
        rf"{re.escape(state_signal)}\s*==\s*(?P<width>\d+)'d(?P<state>\d+)"
    )
    match = state_re.search(term)
    if match is None:
        raise ValueError(f"FSM term has no state comparison: {term[:120]!r}")
    state = int(match.group("state"))
    guard = (term[: match.start()] + term[match.end() :]).strip()
    # Remove the state comparison and clean the surrounding boolean syntax.
    # Calyx emits parenthesized conjunctions, so deleting the comparison can
    # otherwise leave invalid ``()`` or ``(& expr)`` fragments.
    for _ in range(4):
        guard = re.sub(r"\(\s*&", "(", guard)
        guard = re.sub(r"&\s*\)", ")", guard)
        guard = re.sub(r"\(\s*\)", "", guard)
    guard = re.sub(r"^\s*&\s*", "", guard)
    guard = guard.strip()
    return state, guard or "1'b1"


def _replace_assignment(source: str, name: str, replacement: str) -> str:
    pattern = re.compile(rf"assign\s+{re.escape(name)}\s*=.*?;", re.S)
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected one assignment for {name}, found {len(matches)}")
    match = matches[0]
    return source[: match.start()] + replacement + source[match.end() :]


def _next_state_case(
    expr: str,
    state_signal: str,
    next_name: str,
    aliases: dict[str, str],
    alias_cache: dict[str, str],
) -> str:
    body = expr.split("=", 1)[1].rsplit(";", 1)[0]
    width_match = re.search(r"\b(\d+)'d\d+", body)
    if width_match is None:
        raise ValueError("FSM expression has no sized state literal")
    width = width_match.group(1)
    arms: OrderedDict[int, list[tuple[str, str]]] = OrderedDict()
    cursor = 0
    matches = list(NEXT_TERM_RE.finditer(body))
    try:
        for match in matches:
            condition = match.group("cond").strip()
            value = match.group("value")
            for term in _split_or(condition):
                state, guard = _state_guard(term, state_signal, aliases, alias_cache)
                arms.setdefault(state, []).append((guard, value))
            cursor = match.end()
    except ValueError:
        # Some Calyx components encode their schedule as opaque basic-block
        # guard wires rather than explicit state comparisons.  Preserve the
        # original priority with a flat case(1'b1) mux instead of emitting a
        # recursive ternary expression that overwhelms Verilog parsers.
        return _priority_next_case(matches, body[cursor:], next_name)
    if not arms or not re.search(rf"\b{width}'d0\s*$", body[cursor:].strip()):
        raise ValueError("unexpected fsm0_in chain shape")
    lines = [
        "always_comb begin",
        f"  {next_name} = {width}'d0;",
        f"  case ({state_signal})",
    ]
    for state, entries in arms.items():
        lines.append(f"    {width}'d{state}: begin")
        for index, (guard, value) in enumerate(entries):
            keyword = "if" if index == 0 else "else if"
            lines.append(f"      {keyword} ({guard}) {next_name} = {value};")
        lines.append("    end")
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def _priority_next_case(
    matches: list[re.Match[str]], tail: str, next_name: str
) -> str:
    if not matches:
        raise ValueError("FSM expression has no next-state terms")
    defaults = re.findall(r"\d+'d\d+", tail)
    if not defaults:
        raise ValueError("FSM expression has no default state")
    default = defaults[-1]
    lines = [
        "always_comb begin",
        f"  {next_name} = {default};",
        "  case (1'b1)",
    ]
    for match in matches:
        for term in _split_or(match.group("cond").strip()):
            lines.append(
                f"    ({term.strip()}): {next_name} = {match.group('value')};"
            )
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def _write_enable_case(
    expr: str,
    state_signal: str,
    write_name: str,
    aliases: dict[str, str],
    alias_cache: dict[str, str],
) -> str:
    body = expr.split("=", 1)[1].rsplit(";", 1)[0]
    body = _expand_guard_aliases(body, aliases, alias_cache)
    width_match = re.search(r"\b(\d+)'d\d+", body)
    if width_match is None:
        return _priority_write_case(_split_or(body), write_name)
    width = width_match.group(1)
    arms: OrderedDict[int, list[str]] = OrderedDict()
    for term in _split_or(body):
        state, guard = _state_guard(term, state_signal, aliases, alias_cache)
        arms.setdefault(state, []).append(guard)
    if not arms:
        raise ValueError("unexpected fsm0_write_en chain shape")
    lines = [
        "always_comb begin",
        f"  {write_name} = 1'b0;",
        f"  case ({state_signal})",
    ]
    for state, guards in arms.items():
        condition = " | ".join(f"({guard})" for guard in guards)
        lines.append(f"    {width}'d{state}: {write_name} = {condition};")
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def _priority_write_case(terms: list[str], write_name: str) -> str:
    if not terms:
        raise ValueError("FSM write-enable expression has no terms")
    lines = [
        "always_comb begin",
        f"  {write_name} = 1'b0;",
        "  case (1'b1)",
    ]
    for term in terms:
        lines.append(f"    ({term.strip()}): {write_name} = 1'b1;")
    lines.extend(["  endcase", "end"])
    return "\n".join(lines)


def _state_decl_pattern(state_signal: str) -> re.Pattern[str]:
    return re.compile(
        rf"logic(?:\s+\[\d+:0\])?\s+{re.escape(state_signal)}\s*;"
    )


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
    declaration_match = _state_decl_pattern(state_signal).search(source)
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
    width = int(state_matches[0][0])
    if width <= 5:
        # A one- to five-bit FSM has no useful high-state partition.
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
    high_width = width - 5
    declarations = "".join(
        f"wire fsm_hi_{group} = {state_signal}[{width - 1}:5] == "
        f"{high_width}'d{group};\n"
        for group in groups
    )
    declaration_match = _state_decl_pattern(state_signal).search(source)
    if declaration_match is None:
        raise ValueError("expected fsm0_out declaration")
    insert_at = declaration_match.end()
    source = source[:insert_at] + "\n" + declarations + source[insert_at:]
    return source, len(matches)


def _transform_one(source: str, keep_state_copies: bool = False,
                   share_state_decodes: bool = False,
                   hierarchical_state_decodes: bool = False,
                   max_fanout: int | None = None) -> tuple[str, int]:
    next_match = re.search(r"assign\s+(?P<next>fsm\d*_in)\s*=.*?;", source, re.S)
    write_match = re.search(
        r"assign\s+(?P<write>fsm\d*_write_en)\s*=.*?;", source, re.S
    )
    if next_match is None or write_match is None:
        raise ValueError("generated SV does not contain both Calyx FSM assignments")
    next_name = next_match.group("next")
    write_name = write_match.group("write")
    if not next_name.endswith("_in") or not write_name.endswith("_write_en"):
        raise ValueError("unexpected Calyx FSM signal names")
    next_prefix = next_name[: -len("_in")]
    write_prefix = write_name[: -len("_write_en")]
    if next_prefix != write_prefix:
        raise ValueError("next-state and write-enable FSM names disagree")
    next_signal = f"{next_prefix}_out"
    write_signal = next_signal
    aliases = dict(
        re.findall(r"wire\s+(_guard\d+)\s*=\s*([^;]+);", source)
    )
    alias_cache: dict[str, str] = {}
    prefix = ""
    if keep_state_copies:
        declaration_match = _state_decl_pattern(next_signal).search(source)
        if declaration_match is None:
            raise ValueError("expected fsm0_out declaration")
        state_width = int(declaration_match.group(1)) + 1
        prefix = (
            # Keep the named observation points, but let synthesis absorb or
            # replicate the copy wires.  A hard dont_touch barrier forces a
            # physically separate high-fanout network and is therefore not a
            # valid timing experiment for the compiler-generated cone.
            f"(* keep = \"true\" *) wire [{state_width - 1}:0] {next_signal}_decode;\n"
            f"(* keep = \"true\" *) wire [{state_width - 1}:0] {next_signal}_write;\n"
            f"assign {next_signal}_decode = {next_signal};\n"
            f"assign {next_signal}_write = {next_signal};\n"
        )
        next_signal = f"{next_signal}_decode"
        write_signal = f"{write_signal}_write"
    next_replacement = _next_state_case(
        next_match.group(0), next_signal, next_name, aliases, alias_cache
    )
    write_replacement = _write_enable_case(
        write_match.group(0), write_signal, write_name, aliases, alias_cache
    )
    transformed = _replace_assignment(source, next_name, next_replacement)
    transformed = _replace_assignment(transformed, write_name, write_replacement)
    if prefix:
        declaration_match = _state_decl_pattern(f"{next_prefix}_out").search(transformed)
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
        declaration_match = _state_decl_pattern(f"{next_prefix}_out").search(transformed)
        if declaration_match is None:
            raise ValueError("expected one fsm0_out declaration")
        declaration = declaration_match.group(0)
        transformed = transformed.replace(
            declaration,
            f'(* max_fanout = {max_fanout} *) {declaration}',
            1,
        )
    return transformed, shared_count


def transform(source: str, keep_state_copies: bool = False,
              share_state_decodes: bool = False,
              hierarchical_state_decodes: bool = False,
              max_fanout: int | None = None) -> tuple[str, int]:
    """Transform every generated Calyx module containing a schedule FSM.

    The streaming Morty backend preserves multiple generated components in
    one SV file.  Guard and FSM names are module-scoped, so collecting them
    across the whole file would bind one component's aliases to another's.
    Apply the local rewrite independently to each module instead.
    """
    module_re = re.compile(r"(?ms)^\s*module\b.*?^\s*endmodule\b")
    shared_total = 0
    cursor = 0
    chunks: list[str] = []
    for match in module_re.finditer(source):
        chunks.append(source[cursor:match.start()])
        block = match.group(0)
        if re.search(r"assign\s+fsm\d*_in\s*=", block) and re.search(
            r"assign\s+fsm\d*_write_en\s*=", block
        ):
            block, shared = _transform_one(
                block,
                keep_state_copies=keep_state_copies,
                share_state_decodes=share_state_decodes,
                hierarchical_state_decodes=hierarchical_state_decodes,
                max_fanout=max_fanout,
            )
            shared_total += shared
        chunks.append(block)
        cursor = match.end()
    chunks.append(source[cursor:])
    if not list(module_re.finditer(source)):
        if re.search(r"assign\s+fsm\d*_in\s*=", source) and re.search(
            r"assign\s+fsm\d*_write_en\s*=", source
        ):
            return _transform_one(
                source,
                keep_state_copies=keep_state_copies,
                share_state_decodes=share_state_decodes,
                hierarchical_state_decodes=hierarchical_state_decodes,
                max_fanout=max_fanout,
            )
        return source, 0
    return "".join(chunks), shared_total


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
                    "state_logic": "discovered FSM input and write-enable signals",
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
