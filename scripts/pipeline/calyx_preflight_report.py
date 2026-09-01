#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import hashlib
import io
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROHIBITED_OPERATIONS = frozenset(
    {
        "arith.negf",
        "arith.uitofp",
        "math.absi",
        "math.floor",
        "memref.collapse_shape",
        "memref.copy",
        "memref.expand_shape",
        "memref.reinterpret_cast",
    }
)

# Generic operations provide only their decoded names, and bare custom names
# are not guaranteed to be registered in this process. Keep the vocabulary
# explicit so a newly observed operation cannot silently become a clean result.
KNOWN_OPERATIONS = frozenset(
    {
        "affine.apply",
        "arith.addf",
        "arith.addi",
        "arith.andi",
        "arith.bitcast",
        "arith.cmpf",
        "arith.cmpi",
        "arith.constant",
        "arith.divf",
        "arith.divsi",
        "arith.divui",
        "arith.extf",
        "arith.extsi",
        "arith.extui",
        "arith.fptosi",
        "arith.fptoui",
        "arith.index_cast",
        "arith.index_castui",
        "arith.maxf",
        "arith.minf",
        "arith.mulf",
        "arith.muli",
        "arith.negf",
        "arith.ori",
        "arith.remsi",
        "arith.remui",
        "arith.select",
        "arith.shli",
        "arith.shrsi",
        "arith.shrui",
        "arith.sitofp",
        "arith.subf",
        "arith.subi",
        "arith.truncf",
        "arith.trunci",
        "arith.uitofp",
        "arith.xori",
        "builtin.module",
        "cf.assert",
        "cf.br",
        "cf.cond_br",
        "func.call",
        "func.func",
        "func.return",
        "math.absi",
        "math.floor",
        "math.sqrt",
        "memref.alloc",
        "memref.alloca",
        "memref.cast",
        "memref.collapse_shape",
        "memref.copy",
        "memref.dealloc",
        "memref.dim",
        "memref.expand_shape",
        "memref.get_global",
        "memref.global",
        "memref.load",
        "memref.reinterpret_cast",
        "memref.store",
        "memref.subview",
        "scf.condition",
        "scf.execute_region",
        "scf.for",
        "scf.if",
        "scf.parallel",
        "scf.reduce",
        "scf.while",
        "scf.yield",
    }
)

HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
OPERATION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_$.-]*\.[A-Za-z0-9_$.-]+\Z")
IDENTIFIER_CHARS = frozenset("_$.-")
SIGILS = frozenset({"#", "!", "@", "^"})
OPENING_DELIMITERS = {"(": ")", "[": "]", "{": "}", "<": ">"}
CLOSING_DELIMITERS = frozenset(OPENING_DELIMITERS.values())

# Nix substitutes these three values into the checker artifact used by the
# authorization route.  The checked-in source intentionally remains unbound:
# command-line callers may select a candidate executable, but cannot assert
# which executable identity is authorized.
AUTHORIZED_MLIR_OPT_PATH = "@calyxPreflightMlirOptPath@"
AUTHORIZED_MLIR_OPT_VERSION = "@calyxPreflightMlirOptVersion@"
AUTHORIZED_MLIR_OPT_SHA256 = "@calyxPreflightMlirOptSha256@"


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    offset: int


@dataclass(frozen=True)
class SourceOperationCandidate:
    name: str
    offset: int
    token_kind: str


@dataclass(frozen=True)
class AuthoritativeOperation:
    name: str
    source_line: int | None
    source_column: int | None
    parent_index: int | None


class SourceMap:
    def __init__(self, text: str) -> None:
        self.line_starts = [0]
        self.line_starts.extend(
            index + 1 for index, char in enumerate(text) if char == "\n"
        )

    def location(self, offset: int) -> tuple[int, int]:
        line_index = bisect.bisect_right(self.line_starts, offset) - 1
        return line_index + 1, offset - self.line_starts[line_index] + 1


def _location(line: int, column: int) -> dict[str, int]:
    return {"line": line, "column": column}


def _diagnostic(
    kind: str, line: int, column: int, message: str
) -> dict[str, object]:
    return {
        "kind": kind,
        "line": line,
        "column": column,
        "message": message,
    }


def _tokenize(
    text: str, source_map: SourceMap
) -> tuple[list[Token], list[dict[str, object]]]:
    tokens: list[Token] = []
    diagnostics: list[dict[str, object]] = []
    cursor = 0
    while cursor < len(text):
        char = text[cursor]
        if char.isspace():
            cursor += 1
            continue
        if text.startswith("//", cursor):
            newline = text.find("\n", cursor + 2)
            cursor = len(text) if newline == -1 else newline + 1
            continue
        if char == '"':
            start = cursor
            cursor += 1
            decoded: list[str] = []
            malformed: str | None = None
            while cursor < len(text) and text[cursor] != '"':
                if text[cursor] in "\r\n":
                    malformed = "missing closing quote"
                    break
                if text[cursor] == "\\":
                    if cursor + 1 < len(text) and text[cursor + 1] in {'"', "\\"}:
                        decoded.append(text[cursor + 1])
                        cursor += 2
                        continue
                    if cursor + 1 < len(text) and text[cursor + 1] in {"n", "t"}:
                        decoded.append("\n" if text[cursor + 1] == "n" else "\t")
                        cursor += 2
                        continue
                    if (
                        cursor + 2 >= len(text)
                        or text[cursor + 1] not in HEX_DIGITS
                        or text[cursor + 2] not in HEX_DIGITS
                    ):
                        malformed = "escape must contain two hexadecimal digits"
                        break
                    decoded.append(chr(int(text[cursor + 1 : cursor + 3], 16)))
                    cursor += 3
                    continue
                decoded.append(text[cursor])
                cursor += 1
            if malformed is None and cursor < len(text) and text[cursor] == '"':
                tokens.append(Token("string", "".join(decoded), start))
                cursor += 1
                continue
            line, column = source_map.location(start)
            diagnostics.append(
                _diagnostic(
                    "malformed_quoted_operation",
                    line,
                    column,
                    f"malformed quoted operation: {malformed or 'missing closing quote'}",
                )
            )
            newline = text.find("\n", cursor)
            cursor = len(text) if newline == -1 else newline + 1
            continue
        if char == "%":
            start = cursor
            cursor += 1
            while cursor < len(text) and (
                text[cursor].isalnum() or text[cursor] in IDENTIFIER_CHARS
            ):
                cursor += 1
            tokens.append(Token("ssa", text[start:cursor], start))
            continue
        if char.isalpha() or char == "_":
            start = cursor
            cursor += 1
            while cursor < len(text) and (
                text[cursor].isalnum() or text[cursor] in IDENTIFIER_CHARS
            ):
                cursor += 1
            tokens.append(Token("identifier", text[start:cursor], start))
            continue
        if char.isdigit():
            start = cursor
            kind = "number"
            if (
                char == "0"
                and cursor + 2 < len(text)
                and text[cursor + 1] in {"x", "X"}
                and text[cursor + 2] in HEX_DIGITS
            ):
                cursor += 3
                while cursor < len(text) and text[cursor] in HEX_DIGITS:
                    cursor += 1
            else:
                cursor += 1
                while cursor < len(text) and text[cursor].isdigit():
                    cursor += 1
                if cursor < len(text) and text[cursor] == ".":
                    kind = "float"
                    cursor += 1
                    while cursor < len(text) and text[cursor].isdigit():
                        cursor += 1
                    if cursor < len(text) and text[cursor] in {"e", "E"}:
                        exponent = cursor + 1
                        if exponent < len(text) and text[exponent] in {"+", "-"}:
                            exponent += 1
                        if exponent < len(text) and text[exponent].isdigit():
                            cursor = exponent + 1
                            while cursor < len(text) and text[cursor].isdigit():
                                cursor += 1
            tokens.append(Token(kind, text[start:cursor], start))
            continue
        tokens.append(Token("punctuation", char, cursor))
        cursor += 1
    return tokens, diagnostics


def _result_assignment_before(tokens: list[Token], equals_index: int) -> bool:
    cursor = equals_index - 1
    while cursor >= 0:
        if tokens[cursor].kind == "number":
            if cursor == 0 or tokens[cursor - 1].value != ":":
                return False
            cursor -= 2
        if cursor < 0 or tokens[cursor].kind != "ssa":
            return False
        cursor -= 1
        if cursor < 0 or tokens[cursor].value != ",":
            return True
        cursor -= 1
    return False


def _attribute_context(tokens: list[Token]) -> list[bool]:
    brace_pairs: dict[int, int] = {}
    open_braces: list[int] = []
    for index, token in enumerate(tokens):
        if token.value == "{":
            open_braces.append(index)
        elif token.value == "}" and open_braces:
            brace_pairs[open_braces.pop()] = index

    attribute_openings: set[int] = set()
    for opening, closing in brace_pairs.items():
        previous = tokens[opening - 1] if opening else None
        following = tokens[closing + 1] if closing + 1 < len(tokens) else None
        if (previous is not None and previous.value in {"attributes", "<"}) or (
            following is not None and following.value == ":"
        ):
            attribute_openings.add(opening)

    contexts: list[bool] = []
    brace_stack: list[bool] = []
    for index, token in enumerate(tokens):
        contexts.append(any(brace_stack))
        if token.value == "{":
            is_attribute = index in attribute_openings or any(brace_stack)
            brace_stack.append(is_attribute)
        elif token.value == "}" and brace_stack:
            brace_stack.pop()
    return contexts


def _delimiter_pairs(tokens: list[Token]) -> dict[int, int]:
    pairs: dict[int, int] = {}
    stack: list[tuple[str, int]] = []
    for index, token in enumerate(tokens):
        closing = OPENING_DELIMITERS.get(token.value)
        if closing is not None:
            stack.append((closing, index))
            continue
        if token.value not in CLOSING_DELIMITERS:
            continue
        if token.value == ">" and index and tokens[index - 1].value == "-":
            continue
        if stack and stack[-1][0] == token.value:
            _, opening = stack.pop()
            pairs[opening] = index
    return pairs


def _unsigned_integer_is_valid(token: Token) -> bool:
    if token.kind != "number":
        return False
    base = 16 if token.value.lower().startswith("0x") else 10
    return int(token.value, base) <= (1 << 64) - 1


def _parse_location_instance(
    tokens: list[Token],
    start: int,
    end: int,
    delimiter_pairs: dict[int, int],
    location_aliases: frozenset[tuple[str, str]],
) -> int | None:
    if start >= end:
        return None

    first = tokens[start]
    if first.kind == "string":
        cursor = start + 1
        if cursor < end and tokens[cursor].value == ":":
            cursor += 1
            if cursor >= end or not _unsigned_integer_is_valid(tokens[cursor]):
                return None
            cursor += 1
            if cursor >= end or tokens[cursor].value != ":":
                return cursor
            cursor += 1
            if cursor >= end or not _unsigned_integer_is_valid(tokens[cursor]):
                return None
            cursor += 1
            if (
                cursor >= end
                or tokens[cursor].kind != "identifier"
                or tokens[cursor].value != "to"
            ):
                return cursor
            cursor += 1
            if cursor < end and _unsigned_integer_is_valid(tokens[cursor]):
                cursor += 1
            if cursor >= end or tokens[cursor].value != ":":
                return None
            cursor += 1
            if cursor >= end or not _unsigned_integer_is_valid(tokens[cursor]):
                return None
            return cursor + 1
        if cursor < end and tokens[cursor].value == "(":
            nested_closing = delimiter_pairs.get(cursor)
            if nested_closing is None or nested_closing >= end:
                return None
            nested_end = _parse_location_instance(
                tokens,
                cursor + 1,
                nested_closing,
                delimiter_pairs,
                location_aliases,
            )
            if nested_end != nested_closing:
                return None
            return nested_closing + 1
        return cursor

    if first.kind == "identifier" and first.value == "unknown":
        return start + 1

    if first.kind == "identifier" and first.value == "callsite":
        opening = start + 1
        if opening >= end or tokens[opening].value != "(":
            return None
        closing = delimiter_pairs.get(opening)
        if closing is None or closing >= end:
            return None
        caller_end = _parse_location_instance(
            tokens,
            opening + 1,
            closing,
            delimiter_pairs,
            location_aliases,
        )
        if (
            caller_end is None
            or caller_end >= closing
            or tokens[caller_end].kind != "identifier"
            or tokens[caller_end].value != "at"
        ):
            return None
        callee_end = _parse_location_instance(
            tokens,
            caller_end + 1,
            closing,
            delimiter_pairs,
            location_aliases,
        )
        return closing + 1 if callee_end == closing else None

    if first.kind == "identifier" and first.value == "fused":
        cursor = start + 1
        if cursor < end and tokens[cursor].value == "<":
            # Fused metadata is the full MLIR attribute grammar.  The pure
            # scanner has no authoritative parser result, so it must not try
            # to recognize an open-ended subset and silently trust it.
            return None
        if cursor >= end or tokens[cursor].value != "[":
            return None
        fused_closing = delimiter_pairs.get(cursor)
        if fused_closing is None or fused_closing >= end:
            return None
        cursor += 1
        if cursor == fused_closing:
            return fused_closing + 1
        while cursor < fused_closing:
            location_end = _parse_location_instance(
                tokens,
                cursor,
                fused_closing,
                delimiter_pairs,
                location_aliases,
            )
            if location_end is None or location_end > fused_closing:
                return None
            cursor = location_end
            if cursor == fused_closing:
                return fused_closing + 1
            if tokens[cursor].value != ",":
                return None
            cursor += 1
            if cursor == fused_closing:
                return None
        return None

    if (
        first.value == "#"
        and start + 1 < end
        and tokens[start + 1].kind in {"identifier", "number"}
        and (tokens[start + 1].kind, tokens[start + 1].value)
        in location_aliases
    ):
        return start + 2

    return None


def _location_structure_is_valid(
    tokens: list[Token],
    start: int,
    end: int,
    delimiter_pairs: dict[int, int],
    location_aliases: frozenset[tuple[str, str]],
) -> bool:
    return (
        _parse_location_instance(
            tokens, start, end, delimiter_pairs, location_aliases
        )
        == end
    )


def _defined_location_aliases(
    tokens: list[Token], delimiter_pairs: dict[int, int]
) -> frozenset[tuple[str, str]]:
    candidates: list[tuple[tuple[str, str], int, int]] = []
    references: list[
        tuple[tuple[str, str], tuple[str, str]]
    ] = []
    for index, token in enumerate(tokens):
        if (
            token.value != "#"
            or index + 3 >= len(tokens)
            or tokens[index + 1].kind not in {"identifier", "number"}
            or tokens[index + 2].value != "="
        ):
            continue
        name = (tokens[index + 1].kind, tokens[index + 1].value)
        if (
            index + 4 < len(tokens)
            and tokens[index + 3].kind == "identifier"
            and tokens[index + 3].value == "loc"
            and tokens[index + 4].value == "("
        ):
            closing = delimiter_pairs.get(index + 4)
            if closing is not None:
                candidates.append((name, index + 5, closing))
            continue
        if (
            index + 4 < len(tokens)
            and tokens[index + 3].value == "#"
            and tokens[index + 4].kind in {"identifier", "number"}
        ):
            references.append(
                (name, (tokens[index + 4].kind, tokens[index + 4].value))
            )

    aliases: set[tuple[str, str]] = set()
    changed = True
    while changed:
        changed = False
        known_aliases = frozenset(aliases)
        for name, start, end in candidates:
            if name in aliases:
                continue
            if (
                _parse_location_instance(
                    tokens, start, end, delimiter_pairs, known_aliases
                )
                == end
            ):
                aliases.add(name)
                changed = True
        for name, target in references:
            if name not in aliases and target in aliases:
                aliases.add(name)
                changed = True
    return frozenset(aliases)


def _location_context(
    tokens: list[Token], source_map: SourceMap
) -> tuple[list[bool], list[dict[str, object]]]:
    delimiter_pairs = _delimiter_pairs(tokens)
    location_aliases = _defined_location_aliases(tokens, delimiter_pairs)

    contexts = [False] * len(tokens)
    diagnostics: list[dict[str, object]] = []
    for index, token in enumerate(tokens):
        if (
            token.kind != "identifier"
            or token.value != "loc"
            or index + 1 >= len(tokens)
            or tokens[index + 1].value != "("
        ):
            continue
        opening = index + 1
        closing = delimiter_pairs.get(opening)
        line, column = source_map.location(token.offset)
        if closing is None:
            diagnostics.append(
                _diagnostic(
                    "malformed_location",
                    line,
                    column,
                    "unclosed location expression",
                )
            )
            continue
        if not _location_structure_is_valid(
            tokens,
            opening + 1,
            closing,
            delimiter_pairs,
            location_aliases,
        ):
            diagnostics.append(
                _diagnostic(
                    "malformed_location",
                    line,
                    column,
                    "malformed location expression",
                )
            )
            continue
        for context_index in range(opening + 1, closing):
            contexts[context_index] = True
    return contexts, diagnostics


def _record_operation(
    operation: str,
    line: int,
    column: int,
    counts: dict[str, int],
    first_locations: dict[str, dict[str, int]],
) -> None:
    if operation not in PROHIBITED_OPERATIONS:
        return
    counts[operation] = counts.get(operation, 0) + 1
    first_locations.setdefault(operation, _location(line, column))


_CUSTOM_OPERATION_ALIASES = {
    "module": "builtin.module",
    "return": "func.return",
}
_GENERIC_OPERATION_LINE = re.compile(
    r'^[ \t]*(?:%[^=\r\n]*=\s*)?"((?:[^"\\]|\\.)+)"\('
)
_GENERIC_SOURCE_LOCATION = re.compile(
    r'loc\("<stdin>":([0-9]+):([0-9]+)\)\Z'
)
_IMPLICIT_TERMINATORS = frozenset(
    {
        ("scf.for", "scf.yield"),
        ("scf.if", "scf.yield"),
        ("scf.parallel", "scf.reduce"),
    }
)


def _decode_mlir_string_contents(value: str) -> str | None:
    decoded: list[str] = []
    cursor = 0
    while cursor < len(value):
        if value[cursor] != "\\":
            decoded.append(value[cursor])
            cursor += 1
            continue
        if cursor + 1 >= len(value):
            return None
        escaped = value[cursor + 1]
        if escaped in {'"', "\\"}:
            decoded.append(escaped)
            cursor += 2
            continue
        if escaped in {"n", "t"}:
            decoded.append("\n" if escaped == "n" else "\t")
            cursor += 2
            continue
        if (
            cursor + 2 >= len(value)
            or value[cursor + 1] not in HEX_DIGITS
            or value[cursor + 2] not in HEX_DIGITS
        ):
            return None
        decoded.append(chr(int(value[cursor + 1 : cursor + 3], 16)))
        cursor += 3
    return "".join(decoded)


def _terminal_generic_location(
    line: str,
) -> tuple[bool, tuple[int, int] | None]:
    location_start = line.rfind(" loc(")
    if location_start == -1 or not line.endswith(")"):
        return False, None
    location = line[location_start + 1 :]
    source_match = _GENERIC_SOURCE_LOCATION.fullmatch(location)
    if source_match is None:
        return True, None
    return True, (int(source_match.group(1)), int(source_match.group(2)))


def _parse_authoritative_operations(
    generic_text: str,
) -> list[AuthoritativeOperation] | None:
    operations: list[AuthoritativeOperation] = []
    region_stack: list[int] = []
    for raw_line in io.StringIO(generic_text):
        line = raw_line.rstrip("\r\n")
        operation_match = _GENERIC_OPERATION_LINE.match(line)
        if operation_match is not None:
            operation = _decode_mlir_string_contents(
                operation_match.group(1)
            )
            if operation is None or OPERATION_NAME.fullmatch(operation) is None:
                return None
            has_location, source_location = _terminal_generic_location(line)
            parent_index = region_stack[-1] if region_stack else None
            operations.append(
                AuthoritativeOperation(
                    name=operation,
                    source_line=source_location[0]
                    if source_location is not None
                    else None,
                    source_column=source_location[1]
                    if source_location is not None
                    else None,
                    parent_index=parent_index,
                )
            )
            operation_index = len(operations) - 1
            if has_location:
                continue
            if "({" not in line:
                return None
            region_stack.append(operation_index)
            continue

        if region_stack and line.lstrip().startswith("})"):
            has_location, source_location = _terminal_generic_location(line)
            if not has_location:
                continue
            operation_index = region_stack.pop()
            operation = operations[operation_index]
            operations[operation_index] = AuthoritativeOperation(
                name=operation.name,
                source_line=source_location[0]
                if source_location is not None
                else None,
                source_column=source_location[1]
                if source_location is not None
                else None,
                parent_index=operation.parent_index,
            )

    if region_stack:
        return None
    return operations


def _source_operation_candidates(
    text: str, source_map: SourceMap
) -> tuple[list[SourceOperationCandidate], bool]:
    tokens, diagnostics = _tokenize(text, source_map)
    if diagnostics:
        return [], False
    candidates: list[SourceOperationCandidate] = []
    source_location_can_be_spoofed = False
    for token in tokens:
        if token.kind == "string" and token.value == "<stdin>":
            source_location_can_be_spoofed = True
        operation: str | None = None
        if token.kind in {"identifier", "string"}:
            if OPERATION_NAME.fullmatch(token.value) is not None:
                operation = token.value
            elif token.kind == "identifier":
                operation = _CUSTOM_OPERATION_ALIASES.get(token.value)
        if operation is not None:
            candidates.append(
                SourceOperationCandidate(
                    name=operation,
                    offset=token.offset,
                    token_kind=token.kind,
                )
            )
    return candidates, not source_location_can_be_spoofed


def _unique_segment_mapping(
    operation_indices: list[int],
    operations: list[AuthoritativeOperation],
    candidates: list[SourceOperationCandidate],
    lower_candidate: int,
    upper_candidate: int,
) -> list[int] | None:
    left: list[int] = []
    candidate_index = lower_candidate + 1
    for operation_index in operation_indices:
        operation = operations[operation_index].name
        while (
            candidate_index < upper_candidate
            and candidates[candidate_index].name != operation
        ):
            candidate_index += 1
        if candidate_index >= upper_candidate:
            return None
        left.append(candidate_index)
        candidate_index += 1

    right_reversed: list[int] = []
    candidate_index = upper_candidate - 1
    for operation_index in reversed(operation_indices):
        operation = operations[operation_index].name
        while (
            candidate_index > lower_candidate
            and candidates[candidate_index].name != operation
        ):
            candidate_index -= 1
        if candidate_index <= lower_candidate:
            return None
        right_reversed.append(candidate_index)
        candidate_index -= 1
    right = list(reversed(right_reversed))
    return left if left == right else None


def _map_authoritative_operations(
    text: str,
    generic_text: str,
) -> tuple[
    list[AuthoritativeOperation],
    list[SourceOperationCandidate | None],
] | None:
    operations = _parse_authoritative_operations(generic_text)
    if operations is None:
        return None
    source_map = SourceMap(text)
    candidates, trust_source_locations = _source_operation_candidates(
        text, source_map
    )
    if not trust_source_locations and not candidates and operations:
        return None

    candidates_by_location: dict[tuple[int, int], int] = {}
    for index, candidate in enumerate(candidates):
        location = source_map.location(candidate.offset)
        if location in candidates_by_location:
            return None
        candidates_by_location[location] = index

    mapped_indices: list[int | None] = [None] * len(operations)
    synthetic_indices: set[int] = {
        index
        for index, operation in enumerate(operations)
        if operation.name == "builtin.module"
        and operation.parent_index is None
        and operation.source_line == 0
        and operation.source_column == 0
    }
    if trust_source_locations:
        for index, operation in enumerate(operations):
            if index in synthetic_indices:
                continue
            if operation.source_line is None or operation.source_column is None:
                continue
            claimed_location = (
                operation.source_line,
                operation.source_column,
            )
            candidate_index = candidates_by_location.get(claimed_location)
            if (
                candidate_index is not None
                and candidates[candidate_index].name == operation.name
            ):
                mapped_indices[index] = candidate_index
                continue
            if operation.parent_index is None or candidate_index is None:
                continue
            parent = operations[operation.parent_index]
            if (
                (parent.name, operation.name) in _IMPLICIT_TERMINATORS
                and parent.source_line == operation.source_line
                and parent.source_column == operation.source_column
                and candidates[candidate_index].name == parent.name
            ):
                synthetic_indices.add(index)

    anchored = [
        index
        for index, candidate_index in enumerate(mapped_indices)
        if candidate_index is not None
    ]
    previous_candidate = -1
    previous_operation = -1
    for operation_index in [*anchored, len(operations)]:
        next_candidate = (
            int(mapped_indices[operation_index])
            if operation_index < len(operations)
            else len(candidates)
        )
        if next_candidate <= previous_candidate:
            return None
        segment = [
            index
            for index in range(previous_operation + 1, operation_index)
            if index not in synthetic_indices
        ]
        segment_mapping = _unique_segment_mapping(
            segment,
            operations,
            candidates,
            previous_candidate,
            next_candidate,
        )
        if segment_mapping is None:
            return None
        for index, candidate_index in zip(segment, segment_mapping):
            mapped_indices[index] = candidate_index
        previous_operation = operation_index
        previous_candidate = next_candidate

    mapped: list[SourceOperationCandidate | None] = []
    for index, candidate_index in enumerate(mapped_indices):
        if index in synthetic_indices:
            mapped.append(None)
        elif candidate_index is None:
            return None
        else:
            mapped.append(candidates[candidate_index])
    return operations, mapped


def _scan_authoritative_operations(
    text: str,
    generic_text: str,
    *,
    initial_diagnostics: tuple[dict[str, object], ...] = (),
) -> tuple[
    dict[str, int],
    dict[str, dict[str, int]],
    list[dict[str, object]],
]:
    mapping = _map_authoritative_operations(text, generic_text)
    if mapping is None:
        return (
            {},
            {},
            [
                *initial_diagnostics,
                _diagnostic(
                    "operation_source_mapping_failed",
                    1,
                    1,
                    "authoritative operation sequence could not be mapped uniquely to source",
                ),
            ],
        )

    source_map = SourceMap(text)
    operations, mapped = mapping
    counts: dict[str, int] = {}
    first_locations: dict[str, dict[str, int]] = {}
    diagnostics = list(initial_diagnostics)
    for operation, candidate in zip(operations, mapped):
        if candidate is None:
            continue
        line, column = source_map.location(candidate.offset)
        _record_operation(
            operation.name, line, column, counts, first_locations
        )
        if operation.name not in KNOWN_OPERATIONS:
            description = (
                "quoted" if candidate.token_kind == "string" else "custom"
            )
            diagnostics.append(
                _diagnostic(
                    "unknown_operation",
                    line,
                    column,
                    f"unknown {description} operation: {operation.name}",
                )
            )

    diagnostics.sort(key=lambda item: (int(item["line"]), int(item["column"])))
    return (
        dict(sorted(counts.items())),
        dict(sorted(first_locations.items())),
        diagnostics,
    )


def _scan_operations(
    text: str,
    *,
    initial_diagnostics: tuple[dict[str, object], ...] = (),
) -> tuple[
    dict[str, int],
    dict[str, dict[str, int]],
    list[dict[str, object]],
]:
    source_map = SourceMap(text)
    tokens, tokenizer_diagnostics = _tokenize(text, source_map)
    diagnostics = [*initial_diagnostics, *tokenizer_diagnostics]
    attribute_contexts = _attribute_context(tokens)
    location_contexts, location_diagnostics = _location_context(
        tokens, source_map
    )
    diagnostics.extend(location_diagnostics)
    counts: dict[str, int] = {}
    first_locations: dict[str, dict[str, int]] = {}

    for index, token in enumerate(tokens):
        if attribute_contexts[index]:
            continue
        previous = tokens[index - 1] if index else None
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        previous_is_attribute_equals = bool(
            previous is not None
            and previous.value == "="
            and not _result_assignment_before(tokens, index - 1)
        )

        if token.kind == "string":
            if location_contexts[index]:
                continue
            if previous is not None and previous.value == "@":
                continue
            if previous_is_attribute_equals:
                continue
            if OPERATION_NAME.fullmatch(token.value) is None:
                line, column = source_map.location(token.offset)
                diagnostics.append(
                    _diagnostic(
                        "malformed_quoted_operation",
                        line,
                        column,
                        "malformed quoted operation: invalid operation name",
                    )
                )
                continue
            if following is not None and following.value == "=":
                continue

            line, column = source_map.location(token.offset)
            _record_operation(
                token.value, line, column, counts, first_locations
            )
            if token.value not in KNOWN_OPERATIONS:
                diagnostics.append(
                    _diagnostic(
                        "unknown_operation",
                        line,
                        column,
                        f"unknown quoted operation: {token.value}",
                    )
                )
            if following is None or following.value != "(":
                if following is None:
                    malformed_line, malformed_column = line, column
                    message = "quoted operation is missing its operand list"
                else:
                    malformed_line, malformed_column = source_map.location(
                        following.offset
                    )
                    message = "malformed trivia after quoted operation"
                diagnostics.append(
                    _diagnostic(
                        "malformed_trivia",
                        malformed_line,
                        malformed_column,
                        message,
                    )
                )
            continue

        if (
            token.kind != "identifier"
            or OPERATION_NAME.fullmatch(token.value) is None
        ):
            continue
        if previous is not None and previous.value in SIGILS:
            continue
        if following is not None and following.value == "=":
            continue
        if previous_is_attribute_equals:
            continue

        line, column = source_map.location(token.offset)
        _record_operation(token.value, line, column, counts, first_locations)
        if token.value not in KNOWN_OPERATIONS:
            diagnostics.append(
                _diagnostic(
                    "unknown_operation",
                    line,
                    column,
                    f"unknown custom operation: {token.value}",
                )
            )

    diagnostics.sort(key=lambda item: (int(item["line"]), int(item["column"])))
    return (
        dict(sorted(counts.items())),
        dict(sorted(first_locations.items())),
        diagnostics,
    )


def _canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _not_run_parser_validation() -> dict[str, object]:
    return {
        "authorized_identity": None,
        "identity_status": "not_run",
        "input_status": "not_run",
        "observed_identity": None,
    }


def _build_report(
    text: str,
    *,
    parser_validated: bool,
    initial_diagnostics: tuple[dict[str, object], ...] = (),
    parser_validation: dict[str, object] | None = None,
    authoritative_generic: str | None = None,
) -> dict[str, object]:
    if parser_validated and authoritative_generic is not None:
        prohibited_ops, first_locations, scanner_diagnostics = (
            _scan_authoritative_operations(
                text,
                authoritative_generic,
                initial_diagnostics=initial_diagnostics,
            )
        )
    else:
        prohibited_ops, first_locations, scanner_diagnostics = _scan_operations(
            text,
            initial_diagnostics=initial_diagnostics,
        )
    report: dict[str, object] = {
        "schema_version": 3,
        "status": "blocked"
        if prohibited_ops or scanner_diagnostics
        else "ok",
        "prohibited_ops": prohibited_ops,
        "first_locations": first_locations,
        "scanner_diagnostics": scanner_diagnostics,
        "parser_validation": parser_validation
        if parser_validation is not None
        else _not_run_parser_validation(),
    }
    report["sha256"] = hashlib.sha256(_canonical_json(report)).hexdigest()
    return report


def build_report(text: str) -> dict[str, object]:
    """Build a fail-closed report without trusting complex location metadata."""
    return _build_report(text, parser_validated=False)


def _authorized_parser_identity() -> dict[str, str] | None:
    values = (
        AUTHORIZED_MLIR_OPT_PATH,
        AUTHORIZED_MLIR_OPT_VERSION,
        AUTHORIZED_MLIR_OPT_SHA256,
    )
    if any(value.startswith("@calyxPreflight") for value in values):
        return None
    if (
        not AUTHORIZED_MLIR_OPT_PATH.startswith("/nix/store/")
        or re.fullmatch(r"[0-9a-f]{64}", AUTHORIZED_MLIR_OPT_SHA256) is None
        or not AUTHORIZED_MLIR_OPT_VERSION
    ):
        return None
    return {
        "canonical_path": AUTHORIZED_MLIR_OPT_PATH,
        "sha256": AUTHORIZED_MLIR_OPT_SHA256,
        "version": AUTHORIZED_MLIR_OPT_VERSION,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser_validation(
    *,
    authorized: dict[str, str] | None,
    identity_status: str,
    input_status: str,
    observed: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "authorized_identity": authorized,
        "identity_status": identity_status,
        "input_status": input_status,
        "observed_identity": observed,
    }


def _validate_with_authorized_parser(
    text: str, mlir_opt: str | None
) -> tuple[
    bool,
    dict[str, object],
    dict[str, object] | None,
    str | None,
]:
    authorized = _authorized_parser_identity()
    if authorized is None:
        return (
            False,
            _parser_validation(
                authorized=None,
                identity_status="unbound",
                input_status="not_run",
                observed=None,
            ),
            _diagnostic(
                "mlir_parser_identity_unbound",
                1,
                1,
                "authorized MLIR parser identity is not bound by Nix",
            ),
            None,
        )

    candidate = Path(mlir_opt or authorized["canonical_path"])
    try:
        canonical = candidate.resolve(strict=True)
        if not canonical.is_file() or not os.access(canonical, os.X_OK):
            raise OSError("parser is not an executable file")
        observed: dict[str, object] = {
            "canonical_path": str(canonical),
            "sha256": _sha256_file(canonical),
            "version_output": None,
        }
    except (OSError, RuntimeError):
        return (
            False,
            _parser_validation(
                authorized=authorized,
                identity_status="unavailable",
                input_status="not_run",
                observed=None,
            ),
            _diagnostic(
                "mlir_parser_unavailable",
                1,
                1,
                "authorized MLIR parser could not be resolved",
            ),
            None,
        )

    if (
        observed["canonical_path"] != authorized["canonical_path"]
        or observed["sha256"] != authorized["sha256"]
    ):
        return (
            False,
            _parser_validation(
                authorized=authorized,
                identity_status="mismatch",
                input_status="not_run",
                observed=observed,
            ),
            _diagnostic(
                "mlir_parser_identity_mismatch",
                1,
                1,
                "configured MLIR parser does not match the authorized identity",
            ),
            None,
        )

    try:
        version = subprocess.run(
            [str(canonical), "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError:
        return (
            False,
            _parser_validation(
                authorized=authorized,
                identity_status="unavailable",
                input_status="not_run",
                observed=observed,
            ),
            _diagnostic(
                "mlir_parser_unavailable",
                1,
                1,
                "authorized MLIR parser version could not be queried",
            ),
            None,
        )
    version_output = version.stdout.decode("utf-8", errors="replace")
    observed["version_output"] = version_output
    version_match = re.search(
        r"^\s*LLVM version ([^\s]+)\s*$", version_output, re.MULTILINE
    )
    if (
        version.returncode != 0
        or version_match is None
        or version_match.group(1) != authorized["version"]
    ):
        return (
            False,
            _parser_validation(
                authorized=authorized,
                identity_status="mismatch",
                input_status="not_run",
                observed=observed,
            ),
            _diagnostic(
                "mlir_parser_identity_mismatch",
                1,
                1,
                "authorized MLIR parser version output does not match",
            ),
            None,
        )

    try:
        parsed = subprocess.run(
            [
                str(canonical),
                "-mlir-print-op-generic",
                "-mlir-print-debuginfo",
                "-mlir-print-local-scope",
            ],
            input=text.encode("utf-8"),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return (
            False,
            _parser_validation(
                authorized=authorized,
                identity_status="verified",
                input_status="unavailable",
                observed=observed,
            ),
            _diagnostic(
                "mlir_parser_unavailable",
                1,
                1,
                "authorized MLIR parser could not parse input",
            ),
            None,
        )
    if parsed.returncode != 0:
        return (
            False,
            _parser_validation(
                authorized=authorized,
                identity_status="verified",
                input_status="rejected",
                observed=observed,
            ),
            _diagnostic(
                "mlir_parser_rejected",
                1,
                1,
                "authorized MLIR parser rejected input",
            ),
            None,
        )
    try:
        authoritative_generic = parsed.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return (
            False,
            _parser_validation(
                authorized=authorized,
                identity_status="verified",
                input_status="accepted",
                observed=observed,
            ),
            _diagnostic(
                "mlir_parser_output_invalid",
                1,
                1,
                "authorized MLIR parser produced invalid generic output",
            ),
            None,
        )
    return (
        True,
        _parser_validation(
            authorized=authorized,
            identity_status="verified",
            input_status="accepted",
            observed=observed,
        ),
        None,
        authoritative_generic,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report prohibited operations at the SCF-to-Calyx boundary."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--mlir-opt",
        default=None,
        help=(
            "candidate mlir-opt executable; its canonical identity must match "
            "the authorization embedded by Nix"
        ),
    )
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"missing input MLIR: {args.input}")

    text = args.input.read_text(encoding="utf-8")
    (
        parser_validated,
        parser_validation,
        parser_diagnostic,
        authoritative_generic,
    ) = (
        _validate_with_authorized_parser(text, args.mlir_opt)
    )
    report = _build_report(
        text,
        parser_validated=parser_validated,
        initial_diagnostics=(parser_diagnostic,)
        if parser_diagnostic is not None
        else (),
        parser_validation=parser_validation,
        authoritative_generic=authoritative_generic,
    )
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 1 if args.require_clean and report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
